import json
import logging
import time
from google import genai
from tenacity import retry, wait_exponential, stop_after_attempt
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Content, ContentStatus
from app.config import LLM_API_KEY

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "gemini-embedding-001"
client = genai.Client(api_key=LLM_API_KEY)


def build_embedding_text(article: Content) -> str:
    """
    Constructs the text to embed from an article's title and LLM-generated summary.
    Combines title + key_takeaway + summary_points + tags into a single string
    for a rich semantic representation.
    """
    parts = [article.title]
    
    if article.summary:
        try:
            summary_data = json.loads(article.summary)
            
            # Skip inappropriate content
            if not summary_data.get("is_appropriate_ai_news", True):
                return ""
            
            key_takeaway = summary_data.get("key_takeaway", "")
            if key_takeaway:
                parts.append(key_takeaway)
            
            summary_points = summary_data.get("summary_points", [])
            if summary_points:
                parts.append(" ".join(summary_points))
            
            tags = summary_data.get("tags", [])
            if tags:
                parts.append(" ".join(tags))
                
        except json.JSONDecodeError:
            pass
    
    return " | ".join(parts)


@retry(wait=wait_exponential(multiplier=1, min=10, max=60), stop=stop_after_attempt(3), reraise=True)
def generate_embedding(text: str) -> list[float]:
    """Generates a 768-dim embedding vector using Gemini Embedding API."""
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
    )
    return result.embeddings[0].values


def embed_processed_articles(limit: int = 35):
    """
    Finds all PROCESSED articles that don't have embeddings yet,
    generates embeddings via Gemini, and stores them in the database.
    """
    db: Session = SessionLocal()
    
    try:
        # Find processed articles without embeddings
        articles = db.query(Content).filter(
            Content.status == ContentStatus.PROCESSED,
            Content.embedding.is_(None)
        ).limit(limit).all()
        
        if not articles:
            logger.info("No articles need embedding.")
            return
        
        logger.info(f"Embedding {len(articles)} articles...")
        
        for article in articles:
            try:
                text_to_embed = build_embedding_text(article)
                
                if not text_to_embed:
                    logger.info(f"Skipping article '{article.title}' (inappropriate or empty)")
                    continue
                
                # Generate the embedding
                embedding = generate_embedding(text_to_embed)
                
                # Store it
                article.embedding = embedding
                db.commit()
                logger.info(f"Embedded: '{article.title[:60]}...'")
                
            except Exception as e:
                logger.error(f"Failed to embed article '{article.title}': {e}")
                db.rollback()
                
                if "429" in str(e):
                    logger.warning("Rate limit hit during embedding. Stopping batch.")
                    break
            
            # Rate limit: ~12 RPM to stay under free tier limits
            time.sleep(5)
        
    finally:
        db.close()
        logger.info("Embedding batch complete.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    embed_processed_articles(limit=10)
