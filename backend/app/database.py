import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import DATABASE_URL

logger = logging.getLogger(__name__)

# Recommended settings for serverless environments like Neon
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_timeout=30,
    max_overflow=10
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def init_extensions():
    """Enable required PostgreSQL extensions (pgvector)."""
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
        logger.info("PostgreSQL 'vector' extension enabled.")
    except Exception as e:
        logger.warning(f"Could not enable vector extension (may already exist): {e}")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
