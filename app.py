import os
import time
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from flask_cors import CORS
from config import Config
from models import db, ChatSession, Message, Document, QueryAnalytics
from services.document_processor import DocumentProcessor
from services.llm_service import LLMService
from services.rag_service import RAGService
from services.cache_service import CacheService
import json
from langchain_core.callbacks import StreamingStdOutCallbackHandler
from langchain_core.runnables import RunnableConfig

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)

db.init_app(app)

rag_service = RAGService(Config)
cache_service = CacheService()

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/session', methods=['GET'])
def get_session():
    session_id = request.args.get('session_id')
    if not session_id:
        new_session = ChatSession()
        db.session.add(new_session)
        db.session.commit()
        return jsonify({"session_id": new_session.id, "history": []})
    
    session = ChatSession.query.get(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404
        
    history = [{
        "sender": msg.sender,
        "content": msg.content,
        "sources": msg.sources,
        "timestamp": msg.timestamp.isoformat()
    } for msg in session.messages]
    
    return jsonify({"session_id": session.id, "history": history})

@app.route('/api/history', methods=['GET'])
def get_all_sessions():
    sessions = ChatSession.query.order_by(ChatSession.updated_at.desc()).all()
    return jsonify([{
        "id": s.id,
        "updated_at": s.updated_at.isoformat(),
        "preview": s.messages[0].content[:40] + "..." if s.messages else "New Chat"
    } for s in sessions])

@app.route('/api/upload', methods=['POST'])
def upload_files():
    session_id = request.form.get('session_id')
    if not session_id:
        return jsonify({"error": "Session ID required"}), 400
        
    if 'files' not in request.files:
        return jsonify({"error": "No files uploaded"}), 400
        
    files = request.files.getlist('files')
    processed_docs = []
    
    for file in files:
        if file.filename == '':
            continue
            
        filename = file.filename
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{session_id}_{filename}")
        file.save(file_path)
        
        try:
            docs = DocumentProcessor.process_file(file_path)
            rag_service.add_documents(session_id, docs)
            
            new_doc = Document(
                session_id=session_id,
                filename=filename,
                file_path=file_path,
                file_type=filename.split('.')[-1]
            )
            db.session.add(new_doc)
            processed_docs.append(filename)
        except Exception as e:
            return jsonify({"error": f"Error processing {filename}: {str(e)}"}), 500
            
    db.session.commit()
    return jsonify({"message": f"Successfully processed {len(processed_docs)} files", "files": processed_docs})

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    session_id = data.get('session_id')
    question = data.get('question')
    provider = data.get('provider', 'groq')
    model = data.get('model')
    
    if not session_id or not question:
        return jsonify({"error": "Session ID and question are required"}), 400
        
    start_time = time.time()
    
    # Check cache
    cached_res = cache_service.get(session_id, question)
    if cached_res:
        return jsonify(cached_res)
        
    session = ChatSession.query.get(session_id)
    vector_store = rag_service.get_vector_store(session_id)
    
    if not vector_store:
        return jsonify({"answer": "Please upload documents first.", "sources": []})
        
    llm = LLMService.get_llm(provider, model)
    retriever = rag_service.get_retriever(vector_store, llm)
    rag_chain = rag_service.get_rag_chain(llm, retriever)
    
    chat_history = rag_service.format_chat_history(session.messages[-10:]) # last 10 messages
    
    try:
        response = rag_chain.invoke({
            "input": question,
            "chat_history": chat_history
        })
        
        answer = response["answer"]
        sources = []
        for doc in response.get("context", []):
            sources.append({
                "filename": os.path.basename(doc.metadata.get("source", "Unknown")),
                "page": doc.metadata.get("page", 1)
            })
            
        # Deduplicate sources
        unique_sources = list({f"{s['filename']}_{s['page']}": s for s in sources}.values())
        
        # Save messages
        user_msg = Message(session_id=session_id, sender='user', content=question)
        bot_msg = Message(session_id=session_id, sender='bot', content=answer, sources=unique_sources)
        db.session.add(user_msg)
        db.session.add(bot_msg)
        
        # Analytics
        duration = time.time() - start_time
        analytics = QueryAnalytics(
            session_id=session_id,
            query=question,
            response_time=duration,
            num_sources=len(unique_sources),
            answer_length=len(answer)
        )
        db.session.add(analytics)
        db.session.commit()
        
        res = {"answer": answer, "sources": unique_sources}
        cache_service.set(session_id, question, res)
        
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/chat-stream', methods=['POST'])
def chat_stream():
    data = request.json
    session_id = data.get('session_id')
    question = data.get('question')
    provider = data.get('provider', 'groq')
    model = data.get('model')

    if not session_id or not question:
        return jsonify({"error": "Session ID and question are required"}), 400

    session = ChatSession.query.get(session_id)
    vector_store = rag_service.get_vector_store(session_id)
    
    if not vector_store:
        return Response("data: " + json.dumps({"answer": "Please upload documents first."}) + "\n\n", mimetype='text/event-stream')

    llm = LLMService.get_llm(provider, model)
    retriever = rag_service.get_retriever(vector_store, llm)
    rag_chain = rag_service.get_rag_chain(llm, retriever)
    chat_history = rag_service.format_chat_history(session.messages[-10:])

    def generate():
        full_answer = ""
        sources = []
        
        # First get the context (sources)
        # Note: Streaming in retrieval chains can be tricky. 
        # For simplicity, we'll invoke the chain but stream the answer tokens.
        try:
            # We use stream() to get chunks
            for chunk in rag_chain.stream({"input": question, "chat_history": chat_history}):
                # The chunk might be context or answer part
                if "answer" in chunk:
                    ans_part = chunk["answer"]
                    full_answer += ans_part
                    yield f"data: {json.dumps({'token': ans_part})}\n\n"
                
                if "context" in chunk and not sources:
                    for doc in chunk["context"]:
                        sources.append({
                            "filename": os.path.basename(doc.metadata.get("source", "Unknown")),
                            "page": doc.metadata.get("page", 1)
                        })
            
            # Final deduplicated sources
            unique_sources = list({f"{s['filename']}_{s['page']}": s for s in sources}.values())
            
            # Save to DB at the end
            with app.app_context():
                user_msg = Message(session_id=session_id, sender='user', content=question)
                bot_msg = Message(session_id=session_id, sender='bot', content=full_answer, sources=unique_sources)
                db.session.add(user_msg)
                db.session.add(bot_msg)
                db.session.commit()
            
            yield f"data: {json.dumps({'done': True, 'sources': unique_sources})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/api/analytics', methods=['GET'])
def get_analytics():
    session_id = request.args.get('session_id')
    if not session_id:
        return jsonify({"error": "Session ID required"}), 400
        
    analytics = QueryAnalytics.query.filter_by(session_id=session_id).all()
    data = [{
        "query": a.query,
        "response_time": a.response_time,
        "num_sources": a.num_sources,
        "answer_length": a.answer_length,
        "timestamp": a.timestamp.isoformat()
    } for a in analytics]
    
    return jsonify(data)

@app.route('/api/documents', methods=['GET'])
def list_documents():
    session_id = request.args.get('session_id')
    if not session_id:
        return jsonify({"error": "Session ID required"}), 400
    
    docs = Document.query.filter_by(session_id=session_id).all()
    return jsonify([{
        "id": d.id,
        "filename": d.filename,
        "file_type": d.file_type,
        "upload_date": d.upload_date.isoformat()
    } for d in docs])

@app.route('/api/clear-session', methods=['POST'])
def clear_session():
    session_id = request.json.get('session_id')
    session = ChatSession.query.get(session_id)
    if session:
        # Delete vector store files
        path = f"{Config.VECTOR_STORE_PATH}_{session_id}"
        if os.path.exists(path):
            import shutil
            shutil.rmtree(path)
            
        Message.query.filter_by(session_id=session_id).delete()
        Document.query.filter_by(session_id=session_id).delete()
        db.session.commit()
        
    return jsonify({"message": "Session cleared"})

@app.route('/api/delete-session', methods=['POST'])
def delete_session():
    session_id = request.json.get('session_id')
    session = ChatSession.query.get(session_id)
    if session:
        # Delete vector store files
        path = f"{Config.VECTOR_STORE_PATH}_{session_id}"
        if os.path.exists(path):
            import shutil
            shutil.rmtree(path)
        
        # Delete uploaded files for this session
        for doc in session.documents:
            if os.path.exists(doc.file_path):
                os.remove(doc.file_path)
                
        db.session.delete(session)
        db.session.commit()
        return jsonify({"message": "Session deleted successfully"})
    
    return jsonify({"error": "Session not found"}), 404

if __name__ == '__main__':
    app.run(debug=True, port=5000)
