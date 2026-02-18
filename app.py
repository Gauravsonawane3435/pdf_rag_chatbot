import os
import time
from datetime import datetime
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
    # Enable foreign keys for SQLite
    from sqlalchemy import event
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
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
        # Return a potential ID but DON'T save to DB yet (Lazy creation)
        return {"session_id": str(uuid.uuid4()), "history": []}
    
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        # If ID was provided but not in DB, return a fresh slate
        return {"session_id": str(uuid.uuid4()), "history": []}
        
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
    history = []
    for s in sessions:
        # Filter: Only show sessions with actual content (messages or documents)
        if not s.messages and not s.documents:
            continue
            
        # Find the first user message for the title
        title = "New Chat"
        user_msgs = [m for m in s.messages if m.sender == 'user']
        if user_msgs:
            title = user_msgs[0].content[:45] + ("..." if len(user_msgs[0].content) > 45 else "")
        
        history.append({
            "id": s.id,
            "updated_at": s.updated_at.isoformat(),
            "preview": title
        })
    return history

@app.post("/api/upload")
async def upload_files(
    session_id: str = Form(...),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    # Ensure session exists (Lazy creation)
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        session = ChatSession(id=session_id)
        db.add(session)
        db.commit()

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
    if not session:
        # Create session if it doesn't exist yet
        session = ChatSession(id=session_id)
        db.add(session)
        db.commit()
        db.refresh(session)

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
        
        # Update session timestamp
        session.updated_at = datetime.utcnow()
        
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
    if not session:
        # Create session if it doesn't exist yet
        session = ChatSession(id=session_id)
        db.add(session)
        db.commit()
        db.refresh(session)
        
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
                # Update session timestamp
                bg_session = background_db.query(ChatSession).filter(ChatSession.id == session_id).first()
                if bg_session:
                    bg_session.updated_at = datetime.utcnow()
                
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
    if not session_id:
        raise HTTPException(status_code=400, detail="Session ID is required")
        
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    
    if session:
        try:
            print(f"\n[PURGE] Starting permanent deletion for session: {session_id}")
            
            # 1. PERMANENTLY CLEAR CACHES
            # Clear in-memory BM25/Document cache
            rag_service.remove_session_cache(session_id)
            # Clear Redis/In-memory AI response cache
            cache_service.clear_session(session_id)
            print(f"[PURGE] All cache layers cleared for {session_id}")
            
            # 2. DELETE PHYSICAL FILES
            # Extract paths before DB records are gone
            docs_to_delete = list(session.documents)
            for doc in docs_to_delete:
                if doc.file_path and os.path.exists(doc.file_path):
                    try:
                        os.remove(doc.file_path)
                        print(f"[PURGE] Deleted physical file: {doc.file_path}")
                    except Exception as fe:
                        print(f"[ERROR] Failed to delete file {doc.file_path}: {fe}")
            
            # 3. DATABASE PURGE
            # We explicitly delete child records first for maximum safety, 
            # though cascade=all-delete-orphan and ON DELETE CASCADE are active.
            try:
                msg_count = db.query(Message).filter(Message.session_id == session_id).delete()
                doc_count = db.query(Document).filter(Document.session_id == session_id).delete()
                ana_count = db.query(QueryAnalytics).filter(QueryAnalytics.session_id == session_id).delete()
                print(f"[PURGE] DB: Removed {msg_count} messages, {doc_count} docs, {ana_count} analytics")
                
                db.delete(session)
                db.commit()
                print(f"[PURGE] DB: ChatSession {session_id} permanently removed")
            except Exception as dbe:
                db.rollback()
                print(f"[FATAL] Database deletion failed: {dbe}")
                raise dbe
            
            # 4. VECTOR DB CLEANUP (FAISS)
            vector_path = f"{Config.VECTOR_STORE_PATH}_{session_id}"
            if os.path.exists(vector_path):
                import shutil
                try:
                    shutil.rmtree(vector_path, ignore_errors=True)
                    print(f"[PURGE] Filesystem: Vector folder deleted: {vector_path}")
                except Exception as ve:
                    print(f"[ERROR] Failed to delete vector folder {vector_path}: {ve}")

            # 5. KEYWORD INDEX CLEANUP (BM25)
            bm25_cache_path = f"{Config.VECTOR_STORE_PATH}_{session_id}_docs.pkl"
            if os.path.exists(bm25_cache_path):
                try:
                    os.remove(bm25_cache_path)
                    print(f"[PURGE] Filesystem: BM25 index deleted: {bm25_cache_path}")
                except Exception as ce:
                    print(f"[ERROR] Failed to delete BM25 cache {bm25_cache_path}: {ce}")
                
            return {"status": "success", "message": f"Session {session_id} purged from all storage layers"}
            
        except Exception as e:
            print(f"[FATAL ERROR] Total Purge Failure: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Critical error during permanent deletion: {str(e)}")
    
    raise HTTPException(status_code=404, detail="Session not found in Database")

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
    # Use 127.0.0.1 instead of 0.0.0.0 for local runs so the URL is clickable
    host = "127.0.0.1" if not os.environ.get("PORT") else "0.0.0.0"
    print(f"Server starting on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)

