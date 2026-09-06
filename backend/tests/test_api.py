"""Tests for the FastAPI endpoints: health, subscription, articles, stats, chat, and feedback."""

from datetime import UTC
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import app, get_db
from app.database import Base
from app.models import Content, ContentSourceType, ContentStatus, Feedback, Source, User
from tests.conftest import SAMPLE_SUMMARY

# ---------------------------------------------------------------------------
# Override the DB dependency to use test SQLite
# ---------------------------------------------------------------------------

@pytest.fixture()
def test_db():
    """Create a test database and override FastAPI's get_db dependency."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    def override_get_db():
        try:
            yield session
        finally:
            pass  # Don't close — we manage it in the fixture

    app.dependency_overrides[get_db] = override_get_db
    yield session
    session.close()
    engine.dispose()
    app.dependency_overrides.clear()


@pytest.fixture()
def client(test_db):
    """Provide a FastAPI TestClient with overridden DB."""
    return TestClient(app)


@pytest.fixture()
def seeded_db(test_db):
    """Seed the test DB with sample data for article-related endpoint tests."""
    source = Source(
        name="TechCrunch AI",
        source_type=ContentSourceType.RSS,
        url_or_id="https://techcrunch.com/feed",
        is_active=True,
    )
    test_db.add(source)
    test_db.flush()

    from datetime import datetime, timedelta
    for i in range(5):
        article = Content(
            source_id=source.id,
            guid=f"article-{i}",
            title=f"AI News Article {i}",
            url=f"https://example.com/article-{i}",
            published_at=datetime.now(UTC) - timedelta(hours=i),
            summary=SAMPLE_SUMMARY,
            status=ContentStatus.PROCESSED,
            processed_at=datetime.now(UTC) - timedelta(hours=i),
        )
        test_db.add(article)
    test_db.commit()
    return test_db


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------

class TestHealthCheck:
    def test_root_returns_ok(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_health_returns_ok(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_status_returns_observability_data(self, client, seeded_db):
        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("healthy", "degraded")
        assert data["database_connected"] is True
        assert "uptime_seconds" in data
        assert "database_stats" in data
        assert data["database_stats"]["total_articles"] == 5
        assert "last_pipeline_run" in data

    def test_status_returns_db_pipeline_run(self, client, test_db):
        from datetime import UTC, datetime

        from app.models import PipelineRun
        run = PipelineRun(
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            status="success",
            articles_scraped=10,
            articles_processed=8,
            articles_embedded=8,
            digests_delivered=1,
            error_count=0,
            duration_seconds=12.5,
        )
        test_db.add(run)
        test_db.commit()

        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        assert data["last_pipeline_run"]["status"] == "success"
        assert data["last_pipeline_run"]["articles_scraped"] == 10
        assert data["last_pipeline_run"]["errors_last_run"] == 0

    def test_trigger_pipeline_endpoint(self, client):
        with patch("app.api.pipeline_job"):
            response = client.post("/api/cron/trigger")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "started"


# ---------------------------------------------------------------------------
# Subscription Endpoints
# ---------------------------------------------------------------------------

class TestSubscription:
    def test_subscribe_creates_user(self, client, test_db):
        response = client.post("/api/subscribe", json={
            "email": "new@example.com",
            "preferences": ["LLMs", "AI Safety"],
        })
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "new@example.com"
        assert data["preferences"] == ["LLMs", "AI Safety"]
        assert data["is_active"] is True

    def test_subscribe_duplicate_reactivates(self, client, test_db):
        # First subscription
        client.post("/api/subscribe", json={
            "email": "dup@example.com",
            "preferences": ["LLMs"],
        })
        # Unsubscribe
        client.get("/api/unsubscribe?email=dup@example.com")
        # Re-subscribe with new preferences
        response = client.post("/api/subscribe", json={
            "email": "dup@example.com",
            "preferences": ["AI Ethics"],
        })
        data = response.json()
        assert data["is_active"] is True
        assert data["preferences"] == ["AI Ethics"]

    def test_get_preferences(self, client, test_db):
        client.post("/api/subscribe", json={
            "email": "prefs@example.com",
            "preferences": ["LLMs", "OpenAI"],
        })
        response = client.get("/api/preferences/prefs@example.com")
        assert response.status_code == 200
        assert response.json()["preferences"] == ["LLMs", "OpenAI"]

    def test_get_preferences_not_found(self, client, test_db):
        response = client.get("/api/preferences/nonexistent@example.com")
        assert response.status_code == 404

    def test_unsubscribe(self, client, test_db):
        client.post("/api/subscribe", json={
            "email": "unsub@example.com",
            "preferences": [],
        })
        response = client.get("/api/unsubscribe?email=unsub@example.com")
        assert response.status_code == 200
        assert response.json()["status"] == "success"

    def test_unsubscribe_post(self, client, test_db):
        client.post("/api/subscribe", json={
            "email": "unsub_post@example.com",
            "preferences": ["Robotics"],
        })
        response = client.post("/api/unsubscribe", json={"email": "unsub_post@example.com"})
        assert response.status_code == 200
        assert response.json()["status"] == "success"


# ---------------------------------------------------------------------------
# Dashboard Endpoints
# ---------------------------------------------------------------------------

class TestArticles:
    def test_get_articles_paginated(self, client, seeded_db):
        response = client.get("/api/articles?page=1&page_size=3")
        assert response.status_code == 200
        data = response.json()
        assert len(data["articles"]) == 3
        assert data["total"] == 5
        assert data["page"] == 1
        assert data["page_size"] == 3

    def test_get_articles_search(self, client, seeded_db):
        response = client.get("/api/articles?search=Article 0")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert "Article 0" in data["articles"][0]["title"]

    def test_get_articles_source_filter(self, client, seeded_db):
        response = client.get("/api/articles?source=TechCrunch AI")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5  # All articles are from TechCrunch AI

    def test_get_stats(self, client, seeded_db):
        response = client.get("/api/articles/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_articles"] == 5
        assert data["active_sources"] == 1

    def test_get_sources(self, client, seeded_db):
        response = client.get("/api/articles/sources")
        assert response.status_code == 200
        sources = response.json()
        assert len(sources) == 1
        assert sources[0]["name"] == "TechCrunch AI"

    def test_get_tags(self, client, seeded_db):
        response = client.get("/api/articles/tags")
        assert response.status_code == 200
        tags = response.json()
        # All 5 articles share the same tags from SAMPLE_SUMMARY
        assert any(t["tag"] == "OpenAI" for t in tags)
        assert any(t["count"] == 5 for t in tags)


# ---------------------------------------------------------------------------
# Chat Endpoint
# ---------------------------------------------------------------------------

class TestChat:
    @patch("app.rag.chat")
    def test_chat_returns_answer(self, mock_chat, client, test_db):
        """Chat endpoint should return an answer and sources from the RAG pipeline."""
        mock_chat.return_value = {
            "answer": "Based on recent articles, OpenAI has...",
            "sources": [{"id": 1, "title": "Test", "url": "https://example.com", "tags": []}],
        }
        response = client.post("/api/chat", json={"query": "What is OpenAI doing?"})
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "sources" in data

    def test_chat_empty_query_rejected(self, client, test_db):
        """An empty query should return 400."""
        response = client.post("/api/chat", json={"query": "   "})
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# CORS Tests
# ---------------------------------------------------------------------------

class TestCORS:
    def test_cors_allowed_vercel_origin(self, client):
        """Requests from the production Vercel origin should include CORS headers."""
        response = client.get(
            "/api/health",
            headers={"Origin": "https://briefly-ai-newsletter.vercel.app"},
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "https://briefly-ai-newsletter.vercel.app"
        assert response.headers.get("access-control-allow-credentials") == "true"

    def test_cors_preflight_options(self, client):
        """OPTIONS preflight from allowed origin should return 200 with allow methods."""
        response = client.options(
            "/api/subscribe",
            headers={
                "Origin": "https://briefly-ai-newsletter.vercel.app",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "https://briefly-ai-newsletter.vercel.app"
        assert "POST" in response.headers.get("access-control-allow-methods", "")

    def test_cors_disallowed_origin(self, client):
        """Arbitrary unallowed origins should NOT receive access-control-allow-origin."""
        response = client.get(
            "/api/health",
            headers={"Origin": "https://unauthorized-evil-domain.com"},
        )
        assert response.status_code == 200
        assert "access-control-allow-origin" not in response.headers


# ---------------------------------------------------------------------------
# Complexity Serialization Tests
# ---------------------------------------------------------------------------

class TestComplexitySerialization:
    def test_parse_summary_sanitizes_invalid_complexity(self, client, test_db, sample_source):
        """Articles with 0, negative, or missing complexity should return None."""
        import json

        from app.models import Content, ContentStatus

        # Article with 0 complexity (spam or unrated)
        art_zero = Content(
            source_id=sample_source.id,
            guid="zero-001",
            title="Zero Complexity Article",
            url="https://example.com/zero",
            status=ContentStatus.PROCESSED,
            summary=json.dumps({
                "key_takeaway": "Takeaway",
                "summary_points": ["Point 1"],
                "technical_complexity": 0,
                "tags": ["AI"],
            }),
        )
        # Article with valid 4 complexity
        art_valid = Content(
            source_id=sample_source.id,
            guid="valid-001",
            title="Valid Complexity Article",
            url="https://example.com/valid",
            status=ContentStatus.PROCESSED,
            summary=json.dumps({
                "key_takeaway": "Advanced",
                "summary_points": ["Point 1"],
                "technical_complexity": 4,
                "tags": ["AI"],
            }),
        )
        test_db.add_all([art_zero, art_valid])
        test_db.commit()

        response = client.get("/api/articles")
        assert response.status_code == 200
        items = response.json()["articles"]
        zero_item = next(i for i in items if i["title"] == "Zero Complexity Article")
        valid_item = next(i for i in items if i["title"] == "Valid Complexity Article")

        assert zero_item["technical_complexity"] is None
        assert valid_item["technical_complexity"] == 4


# ---------------------------------------------------------------------------
# Phase 5: Token Cryptography Tests
# ---------------------------------------------------------------------------

class TestTokenCryptography:
    """Tests for feedback token generation, verification, and tampering rejection."""

    def test_valid_token_round_trip(self):
        """A freshly generated token should verify successfully."""
        from app.security import generate_feedback_token, verify_feedback_token

        token = generate_feedback_token(user_id=1, content_id=42, rating=1)
        data = verify_feedback_token(token)
        assert data["user_id"] == 1
        assert data["content_id"] == 42
        assert data["rating"] == 1

    def test_negative_rating_token(self):
        """Tokens with rating=-1 should also round-trip correctly."""
        from app.security import generate_feedback_token, verify_feedback_token

        token = generate_feedback_token(user_id=5, content_id=99, rating=-1)
        data = verify_feedback_token(token)
        assert data["rating"] == -1

    def test_tampered_token_rejected(self):
        """A modified token string should raise BadSignature."""
        from itsdangerous import BadSignature

        from app.security import generate_feedback_token, verify_feedback_token

        token = generate_feedback_token(user_id=1, content_id=1, rating=1)
        tampered = token + "TAMPERED"
        with pytest.raises(BadSignature):
            verify_feedback_token(tampered)

    def test_expired_token_rejected(self):
        """A token older than 30 days should raise SignatureExpired."""
        from unittest.mock import patch as mock_patch

        from itsdangerous import SignatureExpired

        from app.security import generate_feedback_token, verify_feedback_token

        token = generate_feedback_token(user_id=1, content_id=1, rating=1)

        # Fast-forward the clock by 31 days
        import time
        with mock_patch("time.time", return_value=time.time() + 31 * 24 * 60 * 60):
            with pytest.raises(SignatureExpired):
                verify_feedback_token(token)

    def test_invalid_rating_rejected(self):
        """generate_feedback_token should reject ratings other than -1 or 1."""
        from app.security import generate_feedback_token

        with pytest.raises(ValueError):
            generate_feedback_token(user_id=1, content_id=1, rating=0)
        with pytest.raises(ValueError):
            generate_feedback_token(user_id=1, content_id=1, rating=2)


# ---------------------------------------------------------------------------
# Phase 5: Feedback Ingestion API Tests
# ---------------------------------------------------------------------------

class TestFeedbackVerify:
    """Tests for GET /api/feedback/verify (non-mutating step)."""

    def test_verify_valid_token(self, client, test_db):
        """Valid token should return article metadata without writing to DB."""
        from app.security import generate_feedback_token

        # Seed a user and article
        source = Source(name="TestSrc", source_type=ContentSourceType.RSS, url_or_id="https://test.com/feed", is_active=True)
        test_db.add(source)
        test_db.flush()

        user = User(email="verify@test.com", preferences=[], is_active=True)
        test_db.add(user)
        test_db.flush()

        article = Content(
            source_id=source.id, guid="verify-001", title="Test Verify Article",
            url="https://example.com/verify", status=ContentStatus.PROCESSED, summary=SAMPLE_SUMMARY,
        )
        test_db.add(article)
        test_db.commit()

        token = generate_feedback_token(user.id, article.id, rating=1)
        response = client.get(f"/api/feedback/verify?token={token}")
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["article_title"] == "Test Verify Article"
        assert data["rating"] == 1

        # Verify NO feedback was written to DB
        fb_count = test_db.query(Feedback).count()
        assert fb_count == 0

    def test_verify_tampered_token_returns_400(self, client, test_db):
        """A tampered token should return 400."""
        response = client.get("/api/feedback/verify?token=INVALID_TOKEN")
        assert response.status_code == 400

    def test_verify_nonexistent_article_returns_404(self, client, test_db):
        """A valid token pointing to a nonexistent content_id should return 404."""
        from app.security import generate_feedback_token

        token = generate_feedback_token(user_id=1, content_id=99999, rating=1)
        response = client.get(f"/api/feedback/verify?token={token}")
        assert response.status_code == 404


class TestFeedbackConfirm:
    """Tests for POST /api/feedback/confirm (mutating step)."""

    def test_confirm_creates_feedback(self, client, test_db):
        """Valid confirm should create a Feedback entry in the database."""
        from app.security import generate_feedback_token

        source = Source(name="ConfSrc", source_type=ContentSourceType.RSS, url_or_id="https://test.com/feed", is_active=True)
        test_db.add(source)
        test_db.flush()

        user = User(email="confirm@test.com", preferences=[], is_active=True)
        test_db.add(user)
        test_db.flush()

        article = Content(
            source_id=source.id, guid="confirm-001", title="Confirm Article",
            url="https://example.com/confirm", status=ContentStatus.PROCESSED, summary=SAMPLE_SUMMARY,
        )
        test_db.add(article)
        test_db.commit()

        token = generate_feedback_token(user.id, article.id, rating=1)
        response = client.post("/api/feedback/confirm", json={"token": token})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["rating"] == 1

        # Verify feedback was written
        fb = test_db.query(Feedback).filter(Feedback.user_id == user.id).first()
        assert fb is not None
        assert fb.rating == 1

    def test_confirm_idempotent_upsert(self, client, test_db):
        """Confirming the same user+article twice should update, not duplicate."""
        from app.security import generate_feedback_token

        source = Source(name="UpsertSrc", source_type=ContentSourceType.RSS, url_or_id="https://test.com/feed", is_active=True)
        test_db.add(source)
        test_db.flush()

        user = User(email="upsert@test.com", preferences=[], is_active=True)
        test_db.add(user)
        test_db.flush()

        article = Content(
            source_id=source.id, guid="upsert-001", title="Upsert Article",
            url="https://example.com/upsert", status=ContentStatus.PROCESSED, summary=SAMPLE_SUMMARY,
        )
        test_db.add(article)
        test_db.commit()

        # First: like
        token_like = generate_feedback_token(user.id, article.id, rating=1)
        response1 = client.post("/api/feedback/confirm", json={"token": token_like})
        assert response1.status_code == 200

        # Second: change to dislike
        token_dislike = generate_feedback_token(user.id, article.id, rating=-1)
        response2 = client.post("/api/feedback/confirm", json={"token": token_dislike})
        assert response2.status_code == 200

        # Should be exactly 1 feedback entry, with updated rating
        fbs = test_db.query(Feedback).filter(
            Feedback.user_id == user.id, Feedback.content_id == article.id
        ).all()
        assert len(fbs) == 1
        assert fbs[0].rating == -1

    def test_confirm_inactive_user_returns_403(self, client, test_db):
        """Inactive users should get 403 Forbidden."""
        from app.security import generate_feedback_token

        source = Source(name="InactiveSrc", source_type=ContentSourceType.RSS, url_or_id="https://test.com/feed", is_active=True)
        test_db.add(source)
        test_db.flush()

        user = User(email="inactive@test.com", preferences=[], is_active=False)
        test_db.add(user)
        test_db.flush()

        article = Content(
            source_id=source.id, guid="inactive-001", title="Inactive Article",
            url="https://example.com/inactive", status=ContentStatus.PROCESSED, summary=SAMPLE_SUMMARY,
        )
        test_db.add(article)
        test_db.commit()

        token = generate_feedback_token(user.id, article.id, rating=1)
        response = client.post("/api/feedback/confirm", json={"token": token})
        assert response.status_code == 403

    def test_confirm_nonexistent_content_returns_404(self, client, test_db):
        """Token pointing to nonexistent content should return 404."""
        from app.security import generate_feedback_token

        user = User(email="noart@test.com", preferences=[], is_active=True)
        test_db.add(user)
        test_db.commit()

        token = generate_feedback_token(user.id, content_id=99999, rating=1)
        response = client.post("/api/feedback/confirm", json={"token": token})
        assert response.status_code == 404

    def test_confirm_tampered_token_returns_400(self, client, test_db):
        """Tampered tokens should return 400."""
        response = client.post("/api/feedback/confirm", json={"token": "TAMPERED_GARBAGE"})
        assert response.status_code == 400
