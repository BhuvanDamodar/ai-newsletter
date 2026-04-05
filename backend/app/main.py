import logging
import time
from apscheduler.schedulers.background import BackgroundScheduler
from app.database import Base, engine

# Import our pipeline scripts
from app.scraper.orchestrator import run_all_scrapers
from app.processor import process_pending_articles
from app.email_service import deliver_daily_digests

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def setup_db():
    logger.info("Initializing database tables...")
    import app.models  # noqa
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified/created.")

def pipeline_job():
    """The master pipeline function that runs daily."""
    logger.info("========== STARTING DAILY AI NEWS PIPELINE ==========")
    
    try:
        # Step 1: Scrape the latest news
        logger.info("--- Step 1: Scraping ---")
        run_all_scrapers()
        
        # Step 2: Read Text and Summarize via LLM
        logger.info("--- Step 2: Processing ---")
        process_pending_articles(limit=35) # Reduced from 50 to 35 to guarantee we don't exceed Render's 15min timeout
        
        # Step 3: Rank by User Profile and Send Emails
        logger.info("--- Step 3: Delivery ---")
        deliver_daily_digests()
        
        logger.info("========== UP TO DATE! PIPELINE COMPLETE ==========")
    except Exception as e:
        logger.error(f"PIPELINE FAILED with error: {e}")

if __name__ == "__main__":
    logger.info("Starting briefly.ainews worker daemon...")
    setup_db()
    
    # ── RUN IMMEDIATELY ON STARTUP FOR TESTING ──
    # logger.info("Triggering pipeline immediately for testing purposes...")
    # pipeline_job()
    
    scheduler = BackgroundScheduler()
    
    # Schedule the master pipeline to run every morning at 7:00 AM
    # (Using Cron style timing)
    scheduler.add_job(
        pipeline_job, 
        trigger='cron', 
        hour=7, 
        minute=0, 
        id='daily_pipeline'
    )
    
    scheduler.start()
    
    logger.info("Scheduler started successfully. System will run every day at 7:00 AM.")
    
    try:
        # Keep the main thread alive so the background scheduler can run
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down worker daemon.")
        scheduler.shutdown()
