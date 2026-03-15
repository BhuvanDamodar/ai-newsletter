import logging
import feedparser
import requests
from io import BytesIO
from datetime import datetime, timezone, timedelta
from dateutil import parser as date_parser
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from bs4 import BeautifulSoup

from app.database import SessionLocal
from app.models import Source, Content, ContentStatus, ContentSourceType

logger = logging.getLogger(__name__)

class GenericRSSScraper:
    def __init__(self, time_window_hours: int = 24):
        self.time_window_hours = time_window_hours

    def fetch_feed_with_user_agent(self, url: str):
        """Fetches an RSS feed using requests with a standard User-Agent to bypass simple blocks (like Reddit)."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            # parse from bytes array
            return feedparser.parse(BytesIO(response.content))
        except Exception as e:
            logger.error(f"Failed to fetch feed {url} with requests: {e}")
            # Fallback to standard feedparser just in case
            return feedparser.parse(url)

    def fetch_and_store(self, db: Session, source: Source):
        """
        Fetches an RSS feed for a given source, parses the entries,
        and stores new articles published within the time window.
        """
        logger.info(f"Fetching RSS feed for source: {source.name} from {source.url_or_id}")
        
        feed = self.fetch_feed_with_user_agent(source.url_or_id)
        
        if feed.bozo and feed.bozo_exception:
            logger.error(f"Error parsing feed for {source.name}: {feed.bozo_exception}")
            # Ensure it's not a fatal error, feedparser sets bozo to 1 for non-well-formed XML
            # but often still successfully parses the entries. We log it and try anyway.
            if not feed.entries:
                return

        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.time_window_hours)
        new_items_count = 0

        for entry in feed.entries:
            try:
                # 1. Parse Published Date
                published_str = entry.get('published', entry.get('updated', None))
                if not published_str:
                    logger.warning(f"Skipping entry in {source.name} - no published date found.")
                    continue
                
                published_at = date_parser.parse(published_str)
                # Ensure timezone aware
                if published_at.tzinfo is None:
                    published_at = published_at.replace(tzinfo=timezone.utc)
                
                # Check if it's within our 24h window
                if published_at < cutoff_time:
                    continue # Too old, skip

                # 2. Extract Data
                title = entry.get('title', 'Unknown Title')
                url = entry.get('link', '')
                guid = entry.get('id', entry.get('guid', url)) # Fallback to URL if no ID
                
                # Try to get the optimal content/description
                content_html = ""
                if 'content' in entry and len(entry.content) > 0:
                     content_html = entry.content[0].value
                elif 'description' in entry:
                     content_html = entry.description
                elif 'summary' in entry:
                     content_html = entry.summary

                # Very basic cleaning: just extract text from HTML for raw_content. 
                # Our processor uses raw_content directly right now.
                soup = BeautifulSoup(content_html, "html.parser")
                clean_text = soup.get_text(separator="\n").strip()

                # 3. Store in Database
                new_article = Content(
                    source_id=source.id,
                    guid=guid,
                    title=title,
                    url=url,
                    published_at=published_at,
                    raw_content=clean_text,
                    status=ContentStatus.PENDING_PROCESSING
                )
                
                db.add(new_article)
                db.commit()
                new_items_count += 1
                logger.info(f"Added new article from {source.name}: '{title}'")

            except IntegrityError:
                # This guid already exists in the database
                db.rollback()
                # logger.debug(f"Article already exists (duplicate guid): {guid}")
                
            except Exception as e:
                db.rollback()
                logger.error(f"Failed to process entry in {source.name}: {e}")

        logger.info(f"Finished {source.name}. Added {new_items_count} new items.")

def run_rss_scrapers():
    """
    Finds all active RSS sources in the database and runs the generic scraper.
    """
    db = SessionLocal()
    rss_sources = db.query(Source).filter(
        Source.is_active == True,
        Source.source_type == ContentSourceType.RSS
    ).all()

    if not rss_sources:
        logger.warning("No active RSS sources found in the database. Please add some!")
        db.close()
        return

    scraper = GenericRSSScraper(time_window_hours=24)
    
    for source in rss_sources:
        try:
            scraper.fetch_and_store(db, source)
        except Exception as e:
            logger.error(f"Critical error scraping {source.name}: {e}")
            
    db.close()
    logger.info("Universal RSS Scraping complete.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_rss_scrapers()
