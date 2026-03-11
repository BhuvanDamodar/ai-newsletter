import logging
import time
from app.database import Base, engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_db():
    logger.info("Initializing database tables...")
    # Import models here so Base knows about them when create_all is called
    import app.models  # noqa
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified/created.")

if __name__ == "__main__":
    logger.info("AI News Aggregator worker starting...")
    setup_db()
    
    # Simple loop to keep container running for now.
    # Later we will add APScheduler jobs here.
    try:
        while True:
            logger.info("Worker heartbeat...")
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Shutting down worker.")
