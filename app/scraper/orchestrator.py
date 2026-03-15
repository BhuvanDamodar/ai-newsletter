import logging
from app.database import SessionLocal, Base, engine
from app.models import Source, ContentSourceType
from app.scraper.rss_scraper import run_rss_scrapers

logger = logging.getLogger(__name__)

def seed_default_sources(db):
    """Checks if sources exist, and if not, seeds the database with defaults."""
    if db.query(Source).count() == 0:
        logger.info("Initializing default RSS Sources in the Database...")
        sources = [
            Source(name="TechCrunch AI", source_type=ContentSourceType.RSS, url_or_id="https://techcrunch.com/category/artificial-intelligence/feed/"),
            Source(name="OpenAI Blog", source_type=ContentSourceType.RSS, url_or_id="https://openai.com/news/rss.xml"),
            Source(name="Anthropic News", source_type=ContentSourceType.RSS, url_or_id="https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_news.xml"),
            Source(name="Reddit r/Artificial", source_type=ContentSourceType.RSS, url_or_id="https://www.reddit.com/r/artificial/new.rss"),
            Source(name="Reddit r/MachineLearning", source_type=ContentSourceType.RSS, url_or_id="https://www.reddit.com/r/MachineLearning/new.rss")
        ]
        db.add_all(sources)
        db.commit()

def run_all_scrapers():
    """Master orchestrator to run all scraping sub-modules."""
    logger.info("Starting Scraper Master Process...")
    
    db = SessionLocal()
    try:
        # Pre-seed defaults if brand new database
        seed_default_sources(db)
        
        # 1. Run Universal RSS Scraper
        logger.info("Running RSS Scraper Module...")
        run_rss_scrapers()

        # 2. (Future) Run Native YouTube Scraper
        # logger.info("Running YouTube Scraper Module...")
        # run_youtube_scrapers()

    except Exception as e:
        logger.error(f"Error in master scraper process: {e}")
    finally:
        db.close()
        logger.info("Scraper Master Process complete.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_all_scrapers()
