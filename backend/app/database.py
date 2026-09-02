import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import DATABASE_URL

logger = logging.getLogger(__name__)

# Recommended settings for serverless environments like Neon, with SQLite fallback support
db_url = DATABASE_URL or "sqlite:///./ainews_local.db"
is_sqlite = "sqlite" in db_url

connect_args = {"check_same_thread": False} if is_sqlite else {}
engine_kwargs = {"connect_args": connect_args} if is_sqlite else {
    "pool_pre_ping": True,
    "pool_recycle": 300,
    "pool_timeout": 30,
    "max_overflow": 10,
}

engine = create_engine(db_url, **engine_kwargs)
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
