import json
import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import func, text
from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_fixed

from app.database import Base, SessionLocal, engine
from app.email_service import EmailDeliverer
from app.main import pipeline_job
from app.models import Content, ContentStatus, Source, User

logger = logging.getLogger(__name__)

@retry(wait=wait_fixed(2), stop=stop_after_attempt(5))
def init_db():
    logger.info("Ensuring database tables are created...")
    # Enable pgvector extension before creating tables
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialization successful.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    
    # Run DB init in the background without blocking FastAPI startup
    def background_db_init():
        try:
            init_db()
        except Exception as e:
            logger.error(f"Could not connect to the database on background startup: {e}")
            
    # Launch in a separate thread so it doesn't block the async event loop
    asyncio.create_task(asyncio.to_thread(background_db_init))
    yield

app = FastAPI(title="AI News API", version="1.0.0", lifespan=lifespan)

# Setup CORS to allow Next.js local development frontend to communicate
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency to get a db session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Pydantic Schemas for API ---
class UserCreate(BaseModel):
    email: str
    preferences: list[str] = []

class UserResponse(BaseModel):
    id: int
    email: str
    preferences: list[str]
    is_active: bool

    model_config = {"from_attributes": True}

class ChatRequest(BaseModel):
    query: str

# --- Phase 1 API Endpoints ---
@app.get("/")
def read_root():
    return {"status": "ok", "message": "AI News API running"}


@app.get("/api/health")
def health_check():
    """Stateless lightweight health check for speculative frontend pre-warming."""
    return {"status": "ok"}


@app.get("/api/status")
def pipeline_status(db: Session = Depends(get_db)):
    """Comprehensive observability health check: DB stats, pipeline execution state, and server uptime."""
    from app.models import PipelineRun
    from app.pipeline_state import get_uptime_seconds, load_state

    db_connected = True
    total_articles = 0
    total_embedded = 0
    active_users = 0
    active_sources = 0
    last_db_run = None

    try:
        total_articles = db.query(func.count(Content.id)).filter(Content.status == ContentStatus.PROCESSED).scalar() or 0
        total_embedded = db.query(func.count(Content.id)).filter(
            Content.status == ContentStatus.PROCESSED,
            Content.embedding.isnot(None),
        ).scalar() or 0
        active_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar() or 0
        active_sources = db.query(func.count(Source.id)).filter(Source.is_active == True).scalar() or 0
        last_db_run = db.query(PipelineRun).order_by(PipelineRun.started_at.desc()).first()
    except Exception as e:
        logger.error(f"DB status query failed: {e}")
        db_connected = False

    if last_db_run:
        last_run_info = {
            "last_run_at": (last_db_run.finished_at or last_db_run.started_at).isoformat(),
            "status": last_db_run.status,
            "articles_scraped": last_db_run.articles_scraped,
            "articles_processed": last_db_run.articles_processed,
            "articles_embedded": last_db_run.articles_embedded,
            "digests_delivered": last_db_run.digests_delivered,
            "errors_last_run": last_db_run.error_count,
            "duration_seconds": last_db_run.duration_seconds,
        }
    else:
        last_run = load_state()
        last_run_info = {
            "last_run_at": last_run.last_run_at,
            "status": last_run.status,
            "articles_scraped": last_run.articles_scraped,
            "articles_processed": last_run.articles_processed,
            "articles_embedded": last_run.articles_embedded,
            "digests_delivered": last_run.digests_delivered,
            "errors_last_run": len(last_run.errors or []),
            "duration_seconds": last_run.duration_seconds,
        }

    return {
        "status": "healthy" if db_connected and last_run_info.get("status") != "failed" else "degraded",
        "database_connected": db_connected,
        "uptime_seconds": get_uptime_seconds(),
        "database_stats": {
            "total_articles": total_articles,
            "total_embedded": total_embedded,
            "active_users": active_users,
            "active_sources": active_sources,
        },
        "last_pipeline_run": last_run_info,
    }


@app.get("/api/cron/trigger")
def trigger_pipeline(background_tasks: BackgroundTasks):
    """Hits this endpoint at 7am via cron-job.org to start the pipeline."""
    background_tasks.add_task(pipeline_job)
    return {"status": "started", "message": "Pipeline triggered in background."}

@app.post("/api/subscribe", response_model=UserResponse)
def subscribe_user(user: UserCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        # Update preferences and reactivate if they were unsubscribed
        existing_user.preferences = user.preferences
        existing_user.is_active = True
        db.commit()
        db.refresh(existing_user)
        return existing_user
        
    # Create new user
    new_user = User(
        email=user.email,
        preferences=user.preferences
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Trigger Welcome Email in the background to prevent blocking the UI
    def send_welcome(email):
        try:
            deliverer = EmailDeliverer()
            deliverer.send_welcome_email(email)
        except Exception as e:
            print(f"Failed to send welcome email to {email}: {e}")
            
    background_tasks.add_task(send_welcome, new_user.email)
        
    return new_user

@app.get("/api/preferences/{email}", response_model=UserResponse)
def get_user_preferences(email: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.get("/api/unsubscribe")
def unsubscribe_user(email: str, db: Session = Depends(get_db)):
    """Handles unsubscribe requests directly from the email footer."""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return {"status": "error", "message": "User not found"}
        
    user.is_active = False
    db.commit()
    return {"status": "success", "message": f"Successfully unsubscribed {email}. You will no longer receive emails."}


# --- Phase 3 API Endpoints: Dashboard + Chat ---

def _parse_summary(summary_json: str | None) -> dict:
    """Safely parse the JSON summary stored on a Content row."""
    if not summary_json:
        return {}
    try:
        return json.loads(summary_json)
    except json.JSONDecodeError:
        return {}


@app.get("/api/articles")
def get_articles(
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    search: str | None = None,
    source: str | None = None,
    tag: str | None = None,
    days: int | None = None,
    db: Session = Depends(get_db),
):
    """Paginated article listing with optional filters for the Dashboard page."""
    query = (
        db.query(Content, Source.name.label("source_name"))
        .outerjoin(Source, Content.source_id == Source.id)
        .filter(Content.status == ContentStatus.PROCESSED)
    )

    # --- Filters ---
    if search:
        query = query.filter(Content.title.ilike(f"%{search}%"))

    if source:
        query = query.filter(Source.name == source)

    if days:
        cutoff = datetime.now(UTC) - timedelta(days=days)
        query = query.filter(Content.published_at >= cutoff)

    # Tag filter requires checking inside the JSON summary
    if tag:
        query = query.filter(Content.summary.ilike(f'%"{tag}"%'))

    # Total count before pagination
    total = query.count()

    # Order by most recent first, then paginate
    rows = (
        query.order_by(Content.published_at.desc().nullslast())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    articles = []
    for content, source_name in rows:
        summary = _parse_summary(content.summary)
        articles.append({
            "id": content.id,
            "title": content.title,
            "url": content.url,
            "source_name": source_name,
            "published_at": content.published_at.isoformat() if content.published_at else None,
            "key_takeaway": summary.get("key_takeaway"),
            "summary_points": summary.get("summary_points"),
            "tags": summary.get("tags"),
            "technical_complexity": summary.get("technical_complexity"),
        })

    return {"articles": articles, "total": total, "page": page, "page_size": page_size}


@app.get("/api/articles/stats")
def get_article_stats(db: Session = Depends(get_db)):
    """Dashboard stats: total articles, today's count, active sources, subscribers."""
    total_articles = db.query(func.count(Content.id)).filter(
        Content.status == ContentStatus.PROCESSED
    ).scalar()

    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    articles_today = db.query(func.count(Content.id)).filter(
        Content.status == ContentStatus.PROCESSED,
        Content.published_at >= today_start,
    ).scalar()

    active_sources = db.query(func.count(Source.id)).filter(Source.is_active == True).scalar()
    active_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar()

    return {
        "total_articles": total_articles or 0,
        "articles_today": articles_today or 0,
        "active_sources": active_sources or 0,
        "active_users": active_users or 0,
    }


@app.get("/api/articles/sources")
def get_article_sources(db: Session = Depends(get_db)):
    """Returns list of active sources for the Dashboard filter dropdown."""
    sources = db.query(Source).filter(Source.is_active == True).all()
    return [{"id": s.id, "name": s.name} for s in sources]


@app.get("/api/articles/tags")
def get_article_tags(db: Session = Depends(get_db)):
    """Extracts and counts all tags from processed article summaries."""
    articles = db.query(Content.summary).filter(
        Content.status == ContentStatus.PROCESSED,
        Content.summary.isnot(None),
    ).all()

    tag_counts: dict[str, int] = {}
    for (summary_json,) in articles:
        summary = _parse_summary(summary_json)
        for tag in summary.get("tags", []):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    # Sort by frequency descending
    sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
    return [{"tag": tag, "count": count} for tag, count in sorted_tags]


@app.post("/api/chat")
def chat_with_news(request: ChatRequest):
    """RAG Chat endpoint: embed query → retrieve similar articles → generate answer."""
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    try:
        from app.rag import chat
        result = chat(request.query)
        return result
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate a response. Please try again.")

