import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks
from tenacity import retry, wait_fixed, stop_after_attempt
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from app.database import engine, SessionLocal, Base
from app.models import User
from app.email_service import EmailDeliverer
from app.main import pipeline_job

logger = logging.getLogger(__name__)

@retry(wait=wait_fixed(2), stop=stop_after_attempt(5))
def init_db():
    logger.info("Ensuring database tables are created...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialization successful.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Handle Neon cold starts with retries
    try:
        init_db()
    except Exception as e:
        logger.error(f"Could not connect to the database on startup: {e}")
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
    preferences: List[str] = []

class UserResponse(BaseModel):
    id: int
    email: str
    preferences: List[str]
    is_active: bool

    class Config:
        from_attributes = True

# --- API Endpoints ---
@app.get("/")
def read_root():
    return {"status": "ok", "message": "AI News API running"}

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
