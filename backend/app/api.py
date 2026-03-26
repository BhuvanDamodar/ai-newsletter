from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from app.database import engine, SessionLocal, Base
from app.models import User
from app.email_service import EmailDeliverer

# This will ensure tables are created on startup if they don't exist
Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI News API", version="1.0.0")

# Setup CORS to allow Next.js local development frontend to communicate
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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

@app.post("/api/subscribe", response_model=UserResponse)
def subscribe_user(user: UserCreate, db: Session = Depends(get_db)):
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
    
    # Trigger Welcome Email
    try:
        deliverer = EmailDeliverer()
        deliverer.send_welcome_email(new_user.email)
    except Exception as e:
        print(f"Failed to send welcome email: {e}")
        
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
