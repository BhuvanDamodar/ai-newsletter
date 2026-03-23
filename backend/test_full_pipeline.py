import logging
from app.processor import process_pending_articles

# Generate test summaries first, then trigger curation and emailing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Running LLM Processor (this will take 30-45 seconds due to sleep delays)...")
    process_pending_articles(limit=2) # Just testing 2 to keep it fast
    print("\nRunning Email Delivery generation...")
    
    # Temporarily override the deliver_daily_digests to output an HTML file instead of console text
    from app.database import SessionLocal
    from app.models import User
    from app.curator import ContentCurator
    from app.email_service import EmailDeliverer
    
    db = SessionLocal()
    curator = ContentCurator()
    deliverer = EmailDeliverer()
    
    user_curation_map = curator.curate_for_all_users(max_articles_per_user=5)
    for user_id, articles in user_curation_map.items():
        if not articles: continue
        user = db.query(User).filter(User.id == user_id).first()
        html_body = deliverer.render_email_html(user, articles)
        with open("test_email_output.html", "w") as f:
            f.write(html_body)
        print(f"Generated test_email_output.html for {user.email}")
    db.close()
