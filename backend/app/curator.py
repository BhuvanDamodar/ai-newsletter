import json
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Content, ContentStatus, Feedback, User

logger = logging.getLogger(__name__)

# ── Conservative Tag Canonicalization ──
# Normalizes obvious linguistic and formatting variants while preserving distinct technical domains.
TAG_CANONICAL_MAP = {
    "llm": "llms",
    "large language model": "llms",
    "large language models": "llms",
    "genai": "generative-ai",
    "generative ai": "generative-ai",
    "rag": "rag",
    "retrieval augmented generation": "rag",
    "agent": "agents",
    "ai agent": "agents",
    "ai agents": "agents",
}


def normalize_tag(tag: str) -> str:
    """Normalize a tag to its canonical form using conservative alias mapping.

    Returns empty string for non-string or empty input.
    Unknown tags are lowercased and stripped but otherwise preserved.
    """
    if not isinstance(tag, str):
        return ""
    cleaned = tag.strip().lower()
    return TAG_CANONICAL_MAP.get(cleaned, cleaned)


class ContentCurator:
    def __init__(self, time_window_hours: int = 24):
        self.time_window_hours = time_window_hours

    def get_recent_processed_content(self, db: Session):
        """Fetches all PROCESSED articles from the past 24 hours."""
        cutoff_time = datetime.now(UTC) - timedelta(hours=self.time_window_hours)
        return db.query(Content).filter(
            Content.status == ContentStatus.PROCESSED,
            Content.processed_at >= cutoff_time
        ).all()

    def _get_learned_tag_affinities(self, db: Session, user_id: int) -> dict[str, int]:
        """Aggregate 60-day historical feedback into per-tag affinity scores.

        Returns a dict mapping normalized tag → net affinity score
        (positive means liked, negative means disliked).
        """
        cutoff = datetime.now(UTC) - timedelta(days=60)
        feedbacks = (
            db.query(Feedback.content_id, Feedback.rating)
            .filter(
                Feedback.user_id == user_id,
                Feedback.created_at >= cutoff,
            )
            .all()
        )

        if not feedbacks:
            return {}

        # Batch-fetch all content IDs from the feedback
        content_ids = [f.content_id for f in feedbacks]
        articles = (
            db.query(Content.id, Content.summary)
            .filter(Content.id.in_(content_ids))
            .all()
        )
        summary_map = {a.id: a.summary for a in articles}

        # Aggregate tag affinities
        tag_affinities: dict[str, int] = {}
        for feedback in feedbacks:
            summary_json = summary_map.get(feedback.content_id)
            if not summary_json:
                continue
            try:
                summary_data = json.loads(summary_json)
                tags = summary_data.get("tags", [])
            except (json.JSONDecodeError, TypeError):
                continue

            for tag in tags:
                norm = normalize_tag(tag)
                if norm:
                    # +1 rating → count as liked, -1 → count as disliked
                    tag_affinities[norm] = tag_affinities.get(norm, 0) + feedback.rating

        return tag_affinities

    def score_content_for_user(
        self,
        article: Content,
        user: User,
        db: Session | None = None,
    ) -> int | dict:
        """
        Calculates a relevance score for an article based on explicit preferences
        and learned tag affinities from historical feedback.

        When db is provided, returns a score_breakdown dict with full explainability.
        When db is None (backward-compatible), returns the integer score.

        Score formula:
            Score = max(0, 1 + explicit_pref_score + clamp(learned_affinity, -4, 4))
        """
        base_score = 1

        # Extract article text and tags
        search_text = article.title.lower()
        article_tags_raw: list[str] = []

        try:
            summary_data = json.loads(article.summary) if article.summary else {}

            # If the LLM flagged this article as spam, vulgar, or completely irrelevant, drop it immediately
            if not summary_data.get("is_appropriate_ai_news", True):
                if db is not None:
                    return {
                        "base": 0,
                        "explicit_preferences": 0,
                        "learned_affinity": 0,
                        "total": 0,
                        "matched_topics": [],
                        "matched_affinity_tags": [],
                    }
                return 0

            search_text += " " + summary_data.get("key_takeaway", "").lower()
            article_tags_raw = summary_data.get("tags", [])
            tags_lower = [t.lower() for t in article_tags_raw]
            search_text += " " + " ".join(tags_lower)
        except json.JSONDecodeError:
            pass

        # ── Explicit Preference Score (+5 per match) ──
        explicit_score = 0
        matched_topics = []
        if user.preferences:
            for pref in user.preferences:
                keyword = pref.lower()
                if keyword in search_text:
                    explicit_score += 5
                    matched_topics.append(pref)

        # ── Learned Tag Affinity (±2 per matching tag, clamped [-4, +4]) ──
        learned_affinity = 0
        matched_affinity_tags = []

        if db is not None:
            tag_affinities = self._get_learned_tag_affinities(db, user.id)

            if tag_affinities:
                article_tags_normalized = [normalize_tag(t) for t in article_tags_raw]
                for norm_tag in article_tags_normalized:
                    if norm_tag and norm_tag in tag_affinities:
                        affinity = tag_affinities[norm_tag]
                        if affinity > 0:
                            learned_affinity += 2
                        elif affinity < 0:
                            learned_affinity -= 2
                        matched_affinity_tags.append(norm_tag)

            # Clamp learned affinity to [-4, +4]
            learned_affinity = max(-4, min(4, learned_affinity))

        total = max(0, base_score + explicit_score + learned_affinity)

        if db is not None:
            return {
                "base": base_score,
                "explicit_preferences": explicit_score,
                "learned_affinity": learned_affinity,
                "total": total,
                "matched_topics": matched_topics,
                "matched_affinity_tags": matched_affinity_tags,
            }

        # Backward-compatible: return just the score when no db session provided
        return total

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

            from app.models import DigestLog
            
            for user in active_users:
                # Fetch IDs of articles this user already received
                sent_logs = db.query(DigestLog.content_id).filter(DigestLog.user_id == user.id).all()
                sent_ids = {log[0] for log in sent_logs}
                
                scored_articles = []
                for article in recent_articles:
                    if article.id in sent_ids:
                        continue # Skip if already sent to this user!
                        
                    # Use the full adaptive scoring with db session
                    breakdown = self.score_content_for_user(article, user, db=db)
                    if isinstance(breakdown, dict):
                        score = breakdown["total"]
                    else:
                        score = breakdown

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
