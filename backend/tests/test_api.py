"""Tests for the FastAPI endpoints: health, subscription, articles, stats, and chat."""

from datetime import UTC
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import app, get_db
from app.database import Base
from app.models import Content, ContentSourceType, ContentStatus, Source
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
