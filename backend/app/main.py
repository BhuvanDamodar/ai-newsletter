import json
import logging
import sys
import time

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import RENDER
from app.database import Base, engine, init_extensions
from app.email_service import EmailDeliverer, deliver_daily_digests
from app.embedder import embed_processed_articles
from app.pipeline_state import record_pipeline_run
from app.processor import process_pending_articles
from app.scraper.orchestrator import run_all_scrapers


class JSONLogFormatter(logging.Formatter):
    """Formats log records as structured JSON for production observability."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)


def setup_logging() -> None:
    """Configures JSON logging in production (RENDER=true) or human-readable format locally."""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    if RENDER:
        handler.setFormatter(JSONLogFormatter(datefmt="%Y-%m-%dT%H:%M:%SZ"))
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

    root_logger.handlers.clear()
    root_logger.addHandler(handler)


setup_logging()
logger = logging.getLogger(__name__)


def setup_db() -> None:
    logger.info("Initializing database tables...")
    init_extensions()  # Enable pgvector extension
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified/created.")


def pipeline_job() -> None:
    """The master pipeline function that runs daily with timing, error alerting, and state tracking."""
    logger.info("========== STARTING DAILY AI NEWS PIPELINE ==========")
    start_time = time.time()
    record_pipeline_run(status="running")

    try:
        # Step 1: Scrape the latest news
        logger.info("--- Step 1: Scraping ---")
        run_all_scrapers()

        # Step 2: Read Text and Summarize via LLM
        logger.info("--- Step 2: Processing ---")
        process_pending_articles(limit=35)

        # Step 2.5: Generate vector embeddings for RAG
        logger.info("--- Step 2.5: Embedding ---")
        embed_processed_articles(limit=35)

        # Step 3: Rank by User Profile and Send Emails
        logger.info("--- Step 3: Delivery ---")
        deliver_daily_digests()

        duration = time.time() - start_time
        record_pipeline_run(status="success", duration_seconds=duration)
        logger.info(f"========== UP TO DATE! PIPELINE COMPLETE ({round(duration, 1)}s) ==========")

    except Exception as e:
        duration = time.time() - start_time
        error_msg = str(e)
        logger.error(f"PIPELINE FAILED with error: {error_msg}")
        record_pipeline_run(status="failed", errors=[error_msg], duration_seconds=duration)

        # Send failure alert email to admin
        try:
            deliverer = EmailDeliverer()
            deliverer.send_pipeline_alert_email(error_message=error_msg, stage="Daily Pipeline")
        except Exception as alert_err:
            logger.error(f"Could not send failure alert email: {alert_err}")

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
