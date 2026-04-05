import json
import logging
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from google import genai
from pydantic import BaseModel, Field

from app.database import engine, SessionLocal
from app.models import Content, ContentStatus
from app.config import LLM_MODEL, LLM_API_KEY

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Pydantic Schema for LLM Output validation ────────────────────────────────
class ArticleSummary(BaseModel):
    is_appropriate_ai_news: bool = Field(description="True if the article is relevant to Artificial Intelligence and does NOT contain vulgar/abusive language. False if it is spam, highly vulgar, or completely unrelated to AI.")
    key_takeaway: str = Field(description="A single sentence explaining the main point of the article. Empty string if is_appropriate_ai_news is False.")
    summary_points: list[str] = Field(description="3 to 5 bullet points summarizing the content. Empty list if is_appropriate_ai_news is False.")
    technical_complexity: int = Field(description="A score from 1 to 5 indicating how technical the article is (1=beginner, 5=highly advanced expert). 0 if is_appropriate_ai_news is False.")
    tags: list[str] = Field(description="3 to 5 tags or keywords relevant to the content. Empty list if is_appropriate_ai_news is False.")

import time

# ── Processing Logic ───────────────────────────────────────────────────────

from tenacity import retry, wait_exponential, stop_after_attempt

client = genai.Client(api_key=LLM_API_KEY)
clean_model = LLM_MODEL.replace("gemini/", "") if "gemini/" in LLM_MODEL else LLM_MODEL

@retry(wait=wait_exponential(multiplier=1, min=15, max=60), stop=stop_after_attempt(3), reraise=True)
def generate_summary(text: str) -> str:
    """Passes raw text to Gemini and returns a verified JSON string matching ArticleSummary."""
    
    clipped_text = text[:15000] if text else "No content provided."
    prompt = f"""You are an expert AI researcher curating a professional news feed. 
First, evaluate if the following text is actually related to Artificial Intelligence AND is free of severe vulgarity or abuse. 
If it is spam, just random reddit venting with no news value, or highly vulgar, set is_appropriate_ai_news to false and leave the rest empty.
If it is good AI news, provide a concise, highly accurate summary.

Text to analyze:
{clipped_text}"""

    response = client.models.generate_content(
        model=clean_model,
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": ArticleSummary,
        },
    )
    
    return response.text

def process_pending_articles(limit: int = 10):
    """Fetches PENDING articles, summarizes them with the LLM, and marks them PROCESSED."""
    db: Session = SessionLocal()
    
    pending_articles = db.query(Content).filter(Content.status == ContentStatus.PENDING_PROCESSING).limit(limit).all()
    
    if not pending_articles:
        logger.info("No pending articles found to process.")
        db.close()
        return

    logger.info(f"Processing {len(pending_articles)} articles...")

    for article in pending_articles:
        logger.info(f"Summarizing: '{article.title}'")
        
        try:
            # We use the raw_content (description) or the title if description is empty
            text_to_summarize = article.raw_content or article.title
            
            # 1. Generate the LLM summary (Validated by Pydantic)
            structured_summary_json = generate_summary(text_to_summarize)
            
            # 2. Update the database record
            article.summary = structured_summary_json
            article.status = ContentStatus.PROCESSED
            article.processed_at = datetime.now(timezone.utc)
            
            # Commit one by one so if one fails, we don't lose the others
            db.commit()
            logger.info("Successfully summarized and saved.")
            
        except Exception as e:
            logger.error(f"Failed to process article '{article.title}': {e}")
            db.rollback()
            
            if "429" in str(e):
                logger.warning("Rate limit (429) hit. Stopping the current batch to prevent further failures and leaving remaining articles pending.")
                break
                
            # Mark as failed so we don't get stuck in an infinite loop trying it
            article.status = ContentStatus.FAILED
            db.commit()
            
        # Add a sleep of 5 seconds between requests (12 RPM) to stay under the 15 RPM free tier limit
        time.sleep(5)

    db.close()
    logger.info("Processing batch complete.")

if __name__ == "__main__":
    # Process a small batch to test
    process_pending_articles(limit=5)
