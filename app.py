import os
import time
import logging
from datetime import datetime
import json
import uuid
from typing import List, Optional
from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException, Depends, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker, Session
from models import Base, ChatSession, Message, Document, QueryAnalytics
from config import Config
from services.document_processor import DocumentProcessor
from services.llm_service import LLMService
from services.rag_service import RAGService
from services.cache_service import CacheService

# Initialize Logger
logger = logging.getLogger(__name__)

# --- Database Setup ---
DATABASE_URL = Config.SQLALCHEMY_DATABASE_URI
is_postgres = DATABASE_URL.startswith("postgresql")
# Masked URL for logging
masked_url = DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL
logger.info(f"[DB] Using database: {masked_url}")

try:
    if is_postgres:
        logger.info(f"[DB] Initializing PostgreSQL engine...")
        # Railway external URLs often require SSL
        engine = create_engine(
            DATABASE_URL, 
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            connect_args={"sslmode": "require"} if "rlwy.net" in DATABASE_URL else {}
        )
    else:
        logger.info(f"[DB] Initializing SQLite engine...")
        engine = create_engine(
            DATABASE_URL, 
            connect_args={"check_same_thread": False}
        )
        # Enable foreign keys for SQLite
        from sqlalchemy import event
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Create tables
    logger.info("[DB] Verifying schemas and creating tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("[DB] Database tables verified/created successfully.")
except Exception as e:
    logger.critical(f"[DB] Critical error during database initialization: {e}")
    # Still initialize SessionLocal so routes don't crash on import, 
    # but they will error when used, which we handle in get_db
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- App Setup ---
app = FastAPI(title="NexRetriever RAG Chatbot")

@app.get("/health")
async def health_check():
    """Service health check for production monitoring"""
    try:
        # Check DB connection
        with engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text("SELECT 1"))
        return {"status": "healthy", "timestamp": datetime.utcnow().isoformat(), "database": "connected"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["*"])

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
    
    try:
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
    except Exception as e:
        logger.error(f"Error in get_session: {e}")
        return JSONResponse(status_code=500, content={"error": f"Database error: {str(e)}"})

@app.get("/api/history")
async def get_all_sessions(db: Session = Depends(get_db)):
    try:
        sessions = db.query(ChatSession).order_by(desc(ChatSession.updated_at)).all()
        history = []
        for s in sessions:
            if not s.messages and not s.documents:
                continue
                
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
    except Exception as e:
        logger.error(f"Error in get_all_sessions: {e}")
        return JSONResponse(status_code=500, content={"error": f"Database error: {str(e)}"})

@app.post("/api/upload")
async def upload_files(
    session_id: str = Form(...),
    use_vision: str = Form("false"),  # Form data comes as string
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = Depends(BackgroundTasks)
):
    try:
        # Ensure session exists (Lazy creation)
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if not session:
            session = ChatSession(id=session_id)
            db.add(session)
            db.commit()

        is_vision_enabled = use_vision.lower() == "true"
        processed_docs = []
        
        for file in files:
            if not file.filename:
                continue
                
            filename = file.filename
            file_path = os.path.join(Config.UPLOAD_FOLDER, f"{session_id}_{filename}")
            
            # 1. Save file synchronously (or async read but wait for save)
            with open(file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
            
            # 2. Add to database immediately so user sees it in the list
            new_doc = Document(
                session_id=session_id,
                filename=filename,
                file_path=file_path,
                file_type=filename.split('.')[-1]
            )
            db.add(new_doc)
            processed_docs.append(filename)
            
            # 3. Queue heavy processing in background
            background_tasks.add_task(
                process_document_background, 
                session_id, 
                file_path, 
                is_vision_enabled
            )
                
        db.commit()
        return {
            "message": f"Successfully uploaded {len(processed_docs)} files. Processing in background...", 
            "files": processed_docs
        }
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return JSONResponse(status_code=500, content={"error": f"Upload failure: {str(e)}"})

# Background processing logic
def process_document_background(session_id: str, file_path: str, use_vision: bool):
    """Heavy lift processing: OCR, Vision, Embeddings, and Vector DB update."""
    try:
        logger.info(f"[Background] Starting processing for {file_path} (Vision: {use_vision})")
        # Process file content (heavy operation)
        docs = DocumentProcessor.process_file(file_path, use_multimodal=use_vision)
        
        # Add to RAG service (heavy operation: embedding)
        rag_service.add_documents(session_id, docs)
        
        logger.info(f"[Background] Completed processing for {file_path}")
    except Exception as e:
        logger.error(f"[Background] Error processing {file_path}: {e}")


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
        
    try:
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if not session:
            logger.info(f"Creating new session for ID: {session_id}")
            session = ChatSession(id=session_id)
            db.add(session)
            db.commit()
            db.refresh(session)

        vector_store = rag_service.get_vector_store(session_id)
        if not vector_store:
            return {"answer": "I couldn't find any documents for this session. Please re-upload your files.", "sources": []}
            
        llm_provider = provider or 'groq'
        llm_model = model or 'llama-3.3-70b-versatile'
        
        # Diagnostic: Check if API Key exists
        api_key_name = f"{llm_provider.upper()}_API_KEY"
        if not os.getenv(api_key_name):
            logger.error(f"Missing API Key: {api_key_name}")
            return JSONResponse(
                status_code=400,
                content={"error": f"Configuration Error: {api_key_name} is not set in the server environment variables."}
            )

        llm = LLMService.get_llm(llm_provider, llm_model)
        if not llm:
            return {"answer": "Chat service is temporarily unavailable. Error initializing LLM.", "sources": []}

        retriever = rag_service.get_retriever(vector_store, llm, session_id, use_hybrid=True)
        rag_chain = rag_service.get_rag_chain(llm, retriever)
        
        # Limit history to prevent context overflow in small models
        chat_history = rag_service.format_chat_history(session.messages[-6:])
        
        logger.info(f"Invoking RAG chain for session {session_id}")
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
        logger.error(f"Error in chat endpoint: {str(e)}", exc_info=True)
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)}
        )

@app.post("/api/chat-stream")
async def chat_stream(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    session_id = data.get('session_id')
    question = data.get('question')
    provider = data.get('provider', 'groq')
    model = data.get('model')

    if not session_id or not question:
        raise HTTPException(status_code=400, detail="Session ID and question are required")

    try:
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if not session:
            session = ChatSession(id=session_id)
            db.add(session)
            db.commit()
            db.refresh(session)
            
        vector_store = rag_service.get_vector_store(session_id)
        if not vector_store:
            async def err_gen():
                yield f"data: {json.dumps({'token': 'Please upload documents first.'})}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"
            return StreamingResponse(err_gen(), media_type="text/event-stream")

        llm_provider = provider or 'groq'
        llm_model = model or 'llama-3.3-70b-versatile'
        
        api_key_name = f"{llm_provider.upper()}_API_KEY"
        if not os.getenv(api_key_name):
            async def err_gen():
                yield f"data: {json.dumps({'error': f'Config Error: {api_key_name} missing'})}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"
            return StreamingResponse(err_gen(), media_type="text/event-stream")

        llm = LLMService.get_llm(llm_provider, llm_model)
        retriever = rag_service.get_retriever(vector_store, llm, session_id, use_hybrid=True)
        rag_chain = rag_service.get_rag_chain(llm, retriever)
        chat_history = rag_service.format_chat_history(session.messages[-6:])

        async def generate():
            full_answer = ""
            sources = []
            try:
                # Use synchronous stream in a wrapper or handle chunks
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
                
                with SessionLocal() as background_db:
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
                logger.error(f"Error in streaming generation: {str(e)}", exc_info=True)
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")
    except Exception as e:
        logger.error(f"Error starting chat stream: {str(e)}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/analytics")
async def get_analytics(session_id: str, db: Session = Depends(get_db)):
    try:
        analytics = db.query(QueryAnalytics).filter(QueryAnalytics.session_id == session_id).all()
        return [{
            "query": a.query,
            "response_time": a.response_time,
            "num_sources": a.num_sources,
            "answer_length": a.answer_length,
            "timestamp": a.timestamp.isoformat()
        } for a in analytics]
    except Exception as e:
        logger.error(f"Analytics error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/documents")
async def list_documents(session_id: str, db: Session = Depends(get_db)):
    try:
        docs = db.query(Document).filter(Document.session_id == session_id).all()
        return [{
            "id": d.id,
            "filename": d.filename,
            "file_type": d.file_type,
            "upload_date": d.upload_date.isoformat()
        } for d in docs]
    except Exception as e:
        logger.error(f"Documents list error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

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

