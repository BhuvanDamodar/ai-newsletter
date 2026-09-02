import enum

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.sql import func

from app.database import Base


class ContentStatus(enum.Enum):
    PENDING_PROCESSING = "PENDING_PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"

class ContentSourceType(enum.Enum):
    RSS = "RSS"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    preferences = Column(JSON, default=list) # List of keywords/topics
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Source(Base):
    __tablename__ = "sources"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    source_type = Column(Enum(ContentSourceType), nullable=False)
    url_or_id = Column(String, nullable=False) # RSS URL
    is_active = Column(Boolean, default=True)

class Content(Base):
    __tablename__ = "content"
    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("sources.id"))
    guid = Column(String, unique=True, index=True) # Unique identifier from source (e.g. video id, rss guid)
    title = Column(String, nullable=False)
    url = Column(String, nullable=False)
    published_at = Column(DateTime(timezone=True))
    
    raw_content = Column(Text, nullable=True) # HTML or JSON transcript
    markdown_content = Column(Text, nullable=True) # Cleaned markdown
    summary = Column(Text, nullable=True) # LLM generated summary
    embedding = Column(Vector(3072), nullable=True) # Gemini embedding vector for RAG (gemini-embedding-001 = 3072 dims)
    
    status = Column(Enum(ContentStatus), default=ContentStatus.PENDING_PROCESSING)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)

class DigestLog(Base):
    __tablename__ = "digest_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    content_id = Column(Integer, ForeignKey("content.id")) # Which content was sent
    sent_at = Column(DateTime(timezone=True), server_default=func.now())

class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    id = Column(Integer, primary_key=True, index=True)
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, default="running")  # "running", "success", "failed"
    articles_scraped = Column(Integer, default=0)
    articles_processed = Column(Integer, default=0)
    articles_embedded = Column(Integer, default=0)
    digests_delivered = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    duration_seconds = Column(Float, default=0.0)
