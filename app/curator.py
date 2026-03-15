import logging
import json
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Content, ContentStatus, User

logger = logging.getLogger(__name__)

class ContentCurator:
    def __init__(self, time_window_hours: int = 24):
        self.time_window_hours = time_window_hours

    def get_recent_processed_content(self, db: Session):
        """Fetches all PROCESSED articles from the past 24 hours."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.time_window_hours)
        return db.query(Content).filter(
            Content.status == ContentStatus.PROCESSED,
            Content.processed_at >= cutoff_time
        ).all()

    def score_content_for_user(self, article: Content, user: User) -> int:
        """
        Calculates a relevance score for an article based on the user's preferences.
        A very simple keyword matching approach for now.
        Can be upgraded to LLM Embeddings or LLM Agent scoring later.
        """
        score = 0
        if not user.preferences:
            return 1 # Default base score if user has no preferences
            
        # Extract text to search inside (title, tags from summary, key takeaway)
        search_text = article.title.lower()
        
        try:
            summary_data = json.loads(article.summary) if article.summary else {}
            search_text += " " + summary_data.get("key_takeaway", "").lower()
            tags = [t.lower() for t in summary_data.get("tags", [])]
            search_text += " " + " ".join(tags)
        except json.JSONDecodeError:
            pass

        # Score based on keyword hits
        for pref in user.preferences:
            keyword = pref.lower()
            if keyword in search_text:
                score += 5 # High weight for explicit topic match
                
        # Base score of 1 just for being new AI news
        return score + 1

    def curate_for_all_users(self, max_articles_per_user: int = 5):
        """
        Finds the top N articles for every active user.
        Returns a dictionary mapping: { user_id: [Content, Content, ...] }
        """
        db = SessionLocal()
        try:
            recent_articles = self.get_recent_processed_content(db)
            if not recent_articles:
                logger.info("No newly processed articles found in the last 24h to curate.")
                return {}

            active_users = db.query(User).filter(User.is_active == True).all()
            if not active_users:
                logger.info("No active users found to curate for.")
                return {}

            user_curation_map = {}

            for user in active_users:
                scored_articles = []
                for article in recent_articles:
                    score = self.score_content_for_user(article, user)
                    if score > 0:
                        scored_articles.append((score, article))
                
                # Sort by score (descending), then by most recently published
                scored_articles.sort(key=lambda x: (x[0], x[1].published_at), reverse=True)
                
                # Take top N
                top_articles = [item[1] for item in scored_articles[:max_articles_per_user]]
                user_curation_map[user.id] = top_articles
                
                logger.info(f"Curated {len(top_articles)} articles for User ID: {user.id}")

            return user_curation_map

        finally:
            db.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    curator = ContentCurator()
    results = curator.curate_for_all_users()
    print("Curation complete. Run emailer to deliver these.")
