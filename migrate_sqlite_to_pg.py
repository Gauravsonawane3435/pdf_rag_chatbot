import os
import sys
from sqlalchemy import create_engine, MetaData, Table, select, text
from sqlalchemy.orm import sessionmaker
from models import Base, ChatSession, Message, Document, QueryAnalytics
from config import Config
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(override=True)

# Source SQLite
SQLITE_URL = 'sqlite:///rag_chatbot.db'
# Destination PostgreSQL is taken from environment variable
PG_URL = os.getenv('DATABASE_URL')

if not PG_URL:
    print("Error: DATABASE_URL environment variable not set.")
    print("Usage: DATABASE_URL=postgresql://user:pass@host:port/dbname python migrate_sqlite_to_pg.py")
    sys.exit(1)

# Ensure postgresql:// prefix
if PG_URL.startswith("postgres://"):
    PG_URL = PG_URL.replace("postgres://", "postgresql://", 1)

is_postgres = PG_URL.startswith("postgresql")

def migrate():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting migration...")
    print(f"Source: {SQLITE_URL}")
    print(f"Destination: {PG_URL.split('@')[-1]} (password hidden)")

    # Initialize engines
    sqlite_engine = create_engine(SQLITE_URL)
    pg_engine = create_engine(PG_URL)

    # Create tables in PG if they don't exist
    Base.metadata.create_all(pg_engine)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Target tables verified.")

    # Sessions
    SqliteSession = sessionmaker(bind=sqlite_engine)
    PgSession = sessionmaker(bind=pg_engine)

    src_db = SqliteSession()
    dst_db = PgSession()

    try:
        # 1. Migrate ChatSessions
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Migrating ChatSessions...")
        sessions = src_db.query(ChatSession).all()
        for s in sessions:
            # Check if exists
            exists = dst_db.query(ChatSession).filter_by(id=s.id).first()
            if not exists:
                new_s = ChatSession(
                    id=s.id,
                    created_at=s.created_at,
                    updated_at=s.updated_at
                )
                dst_db.add(new_s)
        dst_db.commit()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {len(sessions)} sessions processed.")

        # 2. Migrate Messages
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Migrating Messages...")
        messages = src_db.query(Message).all()
        for m in messages:
            exists = dst_db.query(Message).filter_by(id=m.id).first()
            if not exists:
                new_m = Message(
                    id=m.id,
                    session_id=m.session_id,
                    sender=m.sender,
                    content=m.content,
                    sources=m.sources,
                    timestamp=m.timestamp
                )
                dst_db.add(new_m)
        dst_db.commit()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {len(messages)} messages processed.")

        # 3. Migrate Documents
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Migrating Documents...")
        docs = src_db.query(Document).all()
        for d in docs:
            exists = dst_db.query(Document).filter_by(id=d.id).first()
            if not exists:
                new_d = Document(
                    id=d.id,
                    session_id=d.session_id,
                    filename=d.filename,
                    file_path=d.file_path,
                    file_type=d.file_type,
                    upload_date=d.upload_date
                )
                dst_db.add(new_d)
        dst_db.commit()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {len(docs)} documents processed.")

        # 4. Migrate QueryAnalytics
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Migrating QueryAnalytics...")
        analytics = src_db.query(QueryAnalytics).all()
        for a in analytics:
            exists = dst_db.query(QueryAnalytics).filter_by(id=a.id).first()
            if not exists:
                new_a = QueryAnalytics(
                    id=a.id,
                    session_id=a.session_id,
                    query=a.query,
                    response_time=a.response_time,
                    num_sources=a.num_sources,
                    answer_length=a.answer_length,
                    user_rating=a.user_rating,
                    timestamp=a.timestamp
                )
                dst_db.add(new_a)
        dst_db.commit()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {len(analytics)} analytics entries processed.")

        # 5. Reset Sequences for PostgreSQL
        if is_postgres:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Resetting PostgreSQL sequences...")
            for table in ['message', 'document', 'query_analytics']:
                try:
                    dst_db.execute(text(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE(MAX(id), 1))"))
                    dst_db.commit()
                except Exception as seq_err:
                    print(f"Warning: Could not reset sequence for {table}: {seq_err}")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Sequences reset.")

        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] SUCCESS: Migration completed successfully.")
        
    except Exception as e:
        dst_db.rollback()
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] FATAL ERROR during migration: {e}")
        raise e
    finally:
        src_db.close()
        dst_db.close()

if __name__ == "__main__":
    migrate()
