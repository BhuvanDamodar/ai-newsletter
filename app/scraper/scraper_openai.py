"""
OpenAI RSS Feed Scraper
-----------------------
Fetches articles from OpenAI's news and research RSS feeds
and stores them in the project's PostgreSQL database via SQLAlchemy.

Usage:
    # 1. Start Postgres:  docker compose up db -d
    # 2. Run scraper:     uv run python -m app.Scraper.scraper_openai
"""

import feedparser
from app.database import engine, SessionLocal, Base
from app.models import Content, Source, ContentStatus, ContentSourceType

# ── Feed Configuration ──────────────────────────────────────────────────────
# OpenAI provides a single, high-quality official RSS feed that covers
# both product announcements and research.
FEEDS = [
    {
        "name": "OpenAI News & Research",
        "url": "https://openai.com/news/rss.xml",
        "source_type": ContentSourceType.RSS,
    },
]


# ── Database Bootstrap ──────────────────────────────────────────────────────

def ensure_tables():
    """Create all tables if they don't exist yet."""
    Base.metadata.create_all(bind=engine)


def get_or_create_source(db, name: str, url: str, source_type: ContentSourceType) -> Source:
    """Return existing source row or create a new one."""
    source = db.query(Source).filter_by(url_or_id=url).first()
    if not source:
        source = Source(name=name, source_type=source_type, url_or_id=url, is_active=True)
        db.add(source)
        db.commit()
        db.refresh(source)
    return source


# ── Scraping Logic ──────────────────────────────────────────────────────────

def parse_pub_date(date_str: str):
    """Try to parse the RSS pubDate into a timezone-aware datetime."""
    if not date_str:
        return None
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(date_str)
    except Exception:
        return None


def scrape_feed(db, source: Source) -> int:
    """
    Parse a single RSS feed and insert new articles into the content table.
    Returns the number of NEW articles inserted.
    """
    print(f"\nFetching: {source.name}")
    print(f"   URL: {source.url_or_id}")

    feed = feedparser.parse(source.url_or_id)

    if feed.bozo:
        print(f"   Feed had parsing issues: {feed.bozo_exception}")

    new_count = 0

    for entry in feed.entries:
        guid = entry.get("id") or entry.get("link", "")
        title = entry.get("title", "No title")
        link = entry.get("link", "")
        description = entry.get("description", "")
        published = entry.get("published", "")

        if not guid:
            continue

        # Check if already scraped (by guid)
        exists = db.query(Content).filter_by(guid=guid).first()
        if exists:
            continue

        article = Content(
            source_id=source.id,
            guid=guid,
            title=title,
            url=link,
            published_at=parse_pub_date(published),
            raw_content=description,
            status=ContentStatus.PENDING_PROCESSING,
        )
        db.add(article)
        new_count += 1

    db.commit()
    return new_count


# ── Main Entry Point ────────────────────────────────────────────────────────

def scrape_all() -> None:
    """Scrape all configured OpenAI feeds and print a summary."""
    ensure_tables()
    db = SessionLocal()

    print("=" * 60)
    print("AI News Scraper — OpenAI Feeds")
    print("=" * 60)

    total_new = 0
    for feed_cfg in FEEDS:
        source = get_or_create_source(
            db, feed_cfg["name"], feed_cfg["url"], feed_cfg["source_type"]
        )
        new = scrape_feed(db, source)
        total_new += new
        print(f"   {new} new article(s) inserted")

    # ── Summary ─────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"Scrape complete! {total_new} new article(s) added this run.")

    total_openai = 0
    print("\nBreakdown by source:")
    for feed_cfg in FEEDS:
        source = db.query(Source).filter_by(url_or_id=feed_cfg["url"]).first()
        if source:
            count = db.query(Content).filter_by(source_id=source.id).count()
            total_openai += count
            print(f"   - {source.name}: {count} articles")
    
    print(f"\nTotal OpenAI articles in database: {total_openai}")

    # 5 most recent articles
    print("\n5 Most Recent Articles:")
    recent = (
        db.query(Content)
        .join(Source)
        .filter(Content.published_at.isnot(None))
        .filter(Source.name.like("%OpenAI%"))
        .order_by(Content.published_at.desc())
        .limit(5)
        .all()
    )
    for article in recent:
        source = db.query(Source).filter_by(id=article.source_id).first()
        print(f"   [{source.name if source else '?'}] {article.title}")
        print(f"            {article.published_at}")

    print("\n" + "=" * 60)
    db.close()


if __name__ == "__main__":
    scrape_all()
