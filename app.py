import os
import time
import json
import uuid
from typing import List, Optional
from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker, Session
from models import Base, ChatSession, Message, Document, QueryAnalytics
from config import Config
from services.document_processor import DocumentProcessor
from services.llm_service import LLMService
from services.rag_service import RAGService
from services.cache_service import CacheService

# --- Database Setup ---
DATABASE_URL = Config.SQLALCHEMY_DATABASE_URI
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- App Setup ---
app = FastAPI(title="NexRetriever RAG Chatbot")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files and Templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Services
rag_service = RAGService(Config)
cache_service = CacheService()

# Initialize multi-modal processor
DocumentProcessor.set_multimodal_processor(os.getenv('GROQ_API_KEY'))

# --- Routes ---

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/session")
async def get_session(session_id: Optional[str] = None, db: Session = Depends(get_db)):
    if not session_id:
        new_session = ChatSession()
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        return {"session_id": new_session.id, "history": []}
    
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    history = [{
        "sender": msg.sender,
        "content": msg.content,
        "sources": msg.sources,
        "timestamp": msg.timestamp.isoformat()
    } for msg in session.messages]
    
    return {"session_id": session.id, "history": history}

@app.get("/api/history")
async def get_all_sessions(db: Session = Depends(get_db)):
    sessions = db.query(ChatSession).order_by(desc(ChatSession.updated_at)).all()
    return [{
        "id": s.id,
        "updated_at": s.updated_at.isoformat(),
        "preview": s.messages[0].content[:40] + "..." if s.messages else "New Chat"
    } for s in sessions]

@app.post("/api/upload")
async def upload_files(
    session_id: str = Form(...),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    processed_docs = []
    
    for file in files:
        if not file.filename:
            continue
            
        filename = file.filename
        file_path = os.path.join(Config.UPLOAD_FOLDER, f"{session_id}_{filename}")
        
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        try:
            docs = DocumentProcessor.process_file(file_path)
            rag_service.add_documents(session_id, docs)
            
            new_doc = Document(
                session_id=session_id,
                filename=filename,
                file_path=file_path,
                file_type=filename.split('.')[-1]
            )
            db.add(new_doc)
            processed_docs.append(filename)
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Error processing {filename}: {str(e)}")
            
    db.commit()
    return {"message": f"Successfully processed {len(processed_docs)} files", "files": processed_docs}

@app.post("/api/chat")
async def chat(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    session_id = data.get('session_id')
    question = data.get('question')
    provider = data.get('provider', 'groq')
    model = data.get('model')
    
    if not session_id or not question:
        raise HTTPException(status_code=400, detail="Session ID and question are required")
        
    start_time = time.time()
    
    # Check cache
    cached_res = cache_service.get(session_id, question)
    if cached_res:
        return cached_res
        
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    vector_store = rag_service.get_vector_store(session_id)
    
    if not vector_store:
        return {"answer": "Please upload documents first.", "sources": []}
        
    llm = LLMService.get_llm(provider, model)
    retriever = rag_service.get_retriever(vector_store, llm, session_id, use_hybrid=True)
    rag_chain = rag_service.get_rag_chain(llm, retriever)
    
    chat_history = rag_service.format_chat_history(session.messages[-10:])
    
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
            
        unique_sources = list({f"{s['filename']}_{s['page']}": s for s in sources}.values())
        
        user_msg = Message(session_id=session_id, sender='user', content=question)
        bot_msg = Message(session_id=session_id, sender='bot', content=answer, sources=unique_sources)
        db.add(user_msg)
        db.add(bot_msg)
        
        duration = time.time() - start_time
        analytics = QueryAnalytics(
            session_id=session_id,
            query=question,
            response_time=duration,
            num_sources=len(unique_sources),
            answer_length=len(answer)
        )
        db.add(analytics)
        db.commit()
        
        res = {"answer": answer, "sources": unique_sources}
        cache_service.set(session_id, question, res)
        
        return res
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat-stream")
async def chat_stream(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    session_id = data.get('session_id')
    question = data.get('question')
    provider = data.get('provider', 'groq')
    model = data.get('model')

    if not session_id or not question:
        raise HTTPException(status_code=400, detail="Session ID and question are required")

    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    vector_store = rag_service.get_vector_store(session_id)
    
    if not vector_store:
        async def err_gen():
            yield f"data: {json.dumps({'token': 'Please upload documents first.'})}\n\n"
        return StreamingResponse(err_gen(), media_type="text/event-stream")

    llm = LLMService.get_llm(provider, model)
    retriever = rag_service.get_retriever(vector_store, llm, session_id, use_hybrid=True)
    rag_chain = rag_service.get_rag_chain(llm, retriever)
    chat_history = rag_service.format_chat_history(session.messages[-10:])

    async def generate():
        full_answer = ""
        sources = []
        try:
            for chunk in rag_chain.stream({"input": question, "chat_history": chat_history}):
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
            
            unique_sources = list({f"{s['filename']}_{s['page']}": s for s in sources}.values())
            
            # Use a fresh session for the background write
            with SessionLocal() as background_db:
                user_msg = Message(session_id=session_id, sender='user', content=question)
                bot_msg = Message(session_id=session_id, sender='bot', content=full_answer, sources=unique_sources)
                background_db.add(user_msg)
                background_db.add(bot_msg)
                background_db.commit()
            
            yield f"data: {json.dumps({'done': True, 'sources': unique_sources})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

@app.get("/api/analytics")
async def get_analytics(session_id: str, db: Session = Depends(get_db)):
    analytics = db.query(QueryAnalytics).filter(QueryAnalytics.session_id == session_id).all()
    return [{
        "query": a.query,
        "response_time": a.response_time,
        "num_sources": a.num_sources,
        "answer_length": a.answer_length,
        "timestamp": a.timestamp.isoformat()
    } for a in analytics]

@app.get("/api/documents")
async def list_documents(session_id: str, db: Session = Depends(get_db)):
    docs = db.query(Document).filter(Document.session_id == session_id).all()
    return [{
        "id": d.id,
        "filename": d.filename,
        "file_type": d.file_type,
        "upload_date": d.upload_date.isoformat()
    } for d in docs]

@app.post("/api/clear-session")
async def clear_session(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    session_id = data.get('session_id')
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if session:
        path = f"{Config.VECTOR_STORE_PATH}_{session_id}"
        if os.path.exists(path):
            import shutil
            shutil.rmtree(path)
            
        db.query(Message).filter(Message.session_id == session_id).delete()
        db.query(Document).filter(Document.session_id == session_id).delete()
        db.commit()
        
    return {"message": "Session cleared"}

@app.post("/api/delete-session")
async def delete_session(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    session_id = data.get('session_id')
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if session:
        try:
            rag_service.remove_session_cache(session_id)
            
            path = f"{Config.VECTOR_STORE_PATH}_{session_id}"
            if os.path.exists(path):
                import shutil
                try:
                    shutil.rmtree(path)
                except: pass

            cache_path = f"{Config.VECTOR_STORE_PATH}_{session_id}_docs.pkl"
            if os.path.exists(cache_path):
                try: os.remove(cache_path)
                except: pass
            
            for doc in session.documents:
                if doc.file_path and os.path.exists(doc.file_path):
                    try: os.remove(doc.file_path)
                    except: pass
                    
            db.delete(session)
            db.commit()
            return {"message": "Session deleted successfully"}
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=str(e))
    
    raise HTTPException(status_code=404, detail="Session not found")

@app.get("/api/view-pdf/{session_id}/{filename}")
async def view_pdf(session_id: str, filename: str):
    from fastapi.responses import FileResponse
    file_path = os.path.join(Config.UPLOAD_FOLDER, f"{session_id}_{filename}")
    if os.path.exists(file_path) and file_path.endswith('.pdf'):
        return FileResponse(file_path, media_type='application/pdf')
    raise HTTPException(status_code=404, detail="PDF not found")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)

