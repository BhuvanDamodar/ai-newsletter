"""
Shared pytest fixtures for Briefly.ai backend tests.

Uses an in-memory SQLite database to avoid needing PostgreSQL/pgvector
for unit tests. The `embedding` column (pgvector Vector type) is excluded
from SQLite schema since it's a Postgres-only extension; tests that need
embedding behavior mock it at the application layer instead.
"""

import json
from datetime import UTC, datetime, timedelta

import pytest
from pgvector.sqlalchemy import Vector
from sqlalchemy import create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import (
    Content,
    ContentSourceType,
    ContentStatus,
    Source,
    User,
)


# Teach SQLite dialect to compile pgvector Vector type as TEXT
@compiles(Vector, "sqlite")
def _compile_vector_sqlite(type_, compiler, **kw):
    return "TEXT"


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(db_engine):
    """Provide a transactional test database session."""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

SAMPLE_SUMMARY = json.dumps({
    "is_appropriate_ai_news": True,
    "key_takeaway": "OpenAI released a new model with improved reasoning capabilities.",
    "summary_points": [
        "The model shows 2x improvement on math benchmarks.",
        "It is available via API starting today.",
        "Pricing remains competitive with existing models."
    ],
    "technical_complexity": 3,
    "tags": ["OpenAI", "LLMs", "AI Models"]
})

SPAM_SUMMARY = json.dumps({
    "is_appropriate_ai_news": False,
    "key_takeaway": "",
    "summary_points": [],
    "technical_complexity": 0,
    "tags": []
})


@pytest.fixture()
def sample_source(db_session):
    """Insert and return a sample RSS source."""
    source = Source(
        name="TechCrunch AI",
        source_type=ContentSourceType.RSS,
        url_or_id="https://techcrunch.com/category/artificial-intelligence/feed/",
        is_active=True,
    )
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)
    return source


@pytest.fixture()
def sample_user(db_session):
    """Insert and return a sample active user with preferences."""
    user = User(
        email="test@example.com",
        preferences=["OpenAI", "LLMs", "AI Safety"],
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def sample_user_no_prefs(db_session):
    """Insert a user with no preferences."""
    user = User(
        email="nopref@example.com",
        preferences=[],
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def processed_article(db_session, sample_source):
    """Insert and return a PROCESSED article with a valid summary."""
    article = Content(
        source_id=sample_source.id,
        guid="tc-001",
        title="OpenAI releases new reasoning model",
        url="https://techcrunch.com/openai-reasoning",
        published_at=datetime.now(UTC) - timedelta(hours=2),
        raw_content="OpenAI has released a new model...",
        summary=SAMPLE_SUMMARY,
        status=ContentStatus.PROCESSED,
        processed_at=datetime.now(UTC) - timedelta(hours=1),
    )
    db_session.add(article)
    db_session.commit()
    db_session.refresh(article)
    return article


@pytest.fixture()
def spam_article(db_session, sample_source):
    """Insert a PROCESSED article flagged as inappropriate."""
    article = Content(
        source_id=sample_source.id,
        guid="spam-001",
        title="Random unrelated spam post",
        url="https://reddit.com/spam",
        published_at=datetime.now(UTC) - timedelta(hours=3),
        raw_content="Buy crypto now!!!",
        summary=SPAM_SUMMARY,
        status=ContentStatus.PROCESSED,
        processed_at=datetime.now(UTC) - timedelta(hours=2),
    )
    db_session.add(article)
    db_session.commit()
    db_session.refresh(article)
    return article


@pytest.fixture()
def pending_article(db_session, sample_source):
    """Insert a PENDING_PROCESSING article."""
    article = Content(
        source_id=sample_source.id,
        guid="pending-001",
        title="Google announces Gemini 4.0",
        url="https://blog.google/gemini-4",
        published_at=datetime.now(UTC) - timedelta(hours=1),
        raw_content="Google just announced Gemini 4.0 with...",
        status=ContentStatus.PENDING_PROCESSING,
    )
    db_session.add(article)
    db_session.commit()
    db_session.refresh(article)
    return article


@pytest.fixture()
def multiple_articles(db_session, sample_source):
    """Insert multiple processed articles with different tags for scoring tests."""
    articles = []
    data = [
        ("OpenAI launches GPT-5", "openai-gpt5", ["OpenAI", "LLMs", "GPT-5"], 4),
        ("Anthropic safety research update", "anthropic-safety", ["Anthropic", "AI Safety", "Interpretability"], 5),
        ("New AI chip from Nvidia", "nvidia-chip", ["Nvidia", "AI Hardware", "GPU"], 2),
        ("DeepMind protein folding breakthrough", "deepmind-protein", ["DeepMind", "Biology", "AI Research"], 4),
        ("AI Ethics policy in EU", "eu-ethics", ["EU", "AI Ethics", "Policy"], 1),
        ("Hugging Face open model release", "hf-model", ["Hugging Face", "Open Source", "LLMs"], 3),
    ]
    for title, guid, tags, complexity in data:
        summary = json.dumps({
            "is_appropriate_ai_news": True,
            "key_takeaway": f"Summary of {title}.",
            "summary_points": [f"Point about {title}."],
            "technical_complexity": complexity,
            "tags": tags,
        })
        article = Content(
            source_id=sample_source.id,
            guid=guid,
            title=title,
            url=f"https://example.com/{guid}",
            published_at=datetime.now(UTC) - timedelta(hours=len(articles)),
            raw_content=f"Content of {title}",
            summary=summary,
            status=ContentStatus.PROCESSED,
            processed_at=datetime.now(UTC) - timedelta(hours=len(articles)),
        )
        db_session.add(article)
        articles.append(article)
    db_session.commit()
    for a in articles:
        db_session.refresh(a)
    return articles
