from sqlalchemy import Column, String, DateTime, Integer, Text, JSON, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()

class ChatSession(Base):
    __tablename__ = 'chat_session'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    messages = relationship('Message', back_populates='session', cascade="all, delete-orphan")
    documents = relationship('Document', back_populates='session', cascade="all, delete-orphan")
    analytics = relationship('QueryAnalytics', back_populates='session', cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = 'message'
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String(36), ForeignKey('chat_session.id', ondelete="CASCADE"), nullable=False)
    sender = Column(String(10), nullable=False)  # 'user' or 'bot'
    content = Column(Text, nullable=False)
    sources = Column(JSON, nullable=True)  # Store source docs/pages
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    session = relationship('ChatSession', back_populates='messages')

class Document(Base):
    __tablename__ = 'document'
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String(36), ForeignKey('chat_session.id', ondelete="CASCADE"), nullable=False)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_type = Column(String(50))
    upload_date = Column(DateTime, default=datetime.utcnow)
    
    session = relationship('ChatSession', back_populates='documents')

class QueryAnalytics(Base):
    __tablename__ = 'query_analytics'
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String(36), ForeignKey('chat_session.id', ondelete="CASCADE"), nullable=False)
    query = Column(Text)
    response_time = Column(Float)  # in seconds
    num_sources = Column(Integer)
    answer_length = Column(Integer)
    user_rating = Column(Integer, nullable=True)  # 1-5 stars
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    session = relationship('ChatSession', back_populates='analytics')
