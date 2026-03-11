from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey, Enum, Boolean
from sqlalchemy.sql import func
import enum
from app.database import Base

class ContentStatus(enum.Enum):
    PENDING_PROCESSING = "PENDING_PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"

class ContentSourceType(enum.Enum):
    YOUTUBE = "YOUTUBE"
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
    url_or_id = Column(String, nullable=False) # RSS URL or YouTube Channel ID
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
    
    status = Column(Enum(ContentStatus), default=ContentStatus.PENDING_PROCESSING)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)

class DigestLog(Base):
    __tablename__ = "digest_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    content_id = Column(Integer, ForeignKey("content.id")) # Which content was sent
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
