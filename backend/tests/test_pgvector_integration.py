"""Real PostgreSQL + pgvector integration tests.

These tests execute against a real PostgreSQL instance with the pgvector extension
enabled (e.g., in CI or local Docker container), verifying:
- Vector column creation & extension activation
- 3072-dimension vector insertion & persistence
- Dimension constraint enforcement (rejects mismatched dimensions)
- Cosine distance (<=>) ranking & nearest neighbor retrieval
- Content & Source ORM relationships under real Postgres
- PipelineRun table persistence across transactions
"""

import os
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Content, ContentSourceType, ContentStatus, PipelineRun, Source, User

# Resolve test PostgreSQL URL from environment
PG_TEST_URL = os.getenv("TEST_DATABASE_URL") or os.getenv("POSTGRES_TEST_URL")

# Auto-skip if no Postgres test instance is configured or reachable
pytestmark = pytest.mark.skipif(
    not PG_TEST_URL,
    reason="PostgreSQL integration tests require TEST_DATABASE_URL (e.g., in GitHub Actions CI)",
)


@pytest.fixture(scope="module")
def pg_engine():
    """Initializes real PostgreSQL engine and sets up the vector extension and schema."""
    engine = create_engine(PG_TEST_URL, echo=False)
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.commit()

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def pg_session(pg_engine):
    """Provides a transactional database session rolled back or cleared between tests."""
    Session = sessionmaker(bind=pg_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


def test_pgvector_extension_loaded(pg_session):
    """Verifies that the pgvector extension is installed and active in PostgreSQL."""
    result = pg_session.execute(
        text("SELECT extname FROM pg_extension WHERE extname = 'vector';")
    ).scalar()
    assert result == "vector"


def test_insert_3072_dim_vector(pg_session):
    """Verifies that 3072-dimensional embedding vectors can be inserted and retrieved."""
    source = Source(
        name="TechCrunch",
        source_type=ContentSourceType.RSS,
        url_or_id="https://techcrunch.com/feed",
        is_active=True,
    )
    pg_session.add(source)
    pg_session.flush()

    # Create dummy 3072-dimension vector
    dummy_vec = [0.01] * 3072

    article = Content(
        source_id=source.id,
        guid="pg-test-001",
        title="Postgres Vector Test Article",
        url="https://example.com/pg-test",
        published_at=datetime.now(UTC),
        status=ContentStatus.PROCESSED,
        embedding=dummy_vec,
    )
    pg_session.add(article)
    pg_session.commit()

    saved = pg_session.query(Content).filter(Content.guid == "pg-test-001").first()
    assert saved is not None
    assert saved.embedding is not None
    assert len(saved.embedding) == 3072
    assert abs(saved.embedding[0] - 0.01) < 1e-5


def test_dimension_constraint_rejects_mismatch(pg_session):
    """Verifies that pgvector rejects vectors with incorrect dimension counts."""
    source = pg_session.query(Source).first()

    # Create invalid vector of dimension 1536 instead of 3072
    invalid_vec = [0.01] * 1536

    article = Content(
        source_id=source.id,
        guid="pg-test-mismatch",
        title="Mismatch Dimension Article",
        url="https://example.com/mismatch",
        status=ContentStatus.PROCESSED,
        embedding=invalid_vec,
    )
    pg_session.add(article)
    with pytest.raises(Exception):
        pg_session.commit()
    pg_session.rollback()


def test_cosine_distance_nearest_neighbor_ranking(pg_session):
    """Verifies that pgvector cosine distance (<=>) correctly ranks the nearest article."""
    source = pg_session.query(Source).first()

    # Vector A: heavily positive in first dimensions
    vec_a = [1.0] * 100 + [0.0] * 2972
    # Vector B: heavily negative in first dimensions
    vec_b = [-1.0] * 100 + [0.0] * 2972

    art_a = Content(
        source_id=source.id,
        guid="art-positive",
        title="Positive Topic Article",
        url="https://example.com/a",
        status=ContentStatus.PROCESSED,
        embedding=vec_a,
    )
    art_b = Content(
        source_id=source.id,
        guid="art-negative",
        title="Negative Topic Article",
        url="https://example.com/b",
        status=ContentStatus.PROCESSED,
        embedding=vec_b,
    )
    pg_session.add_all([art_a, art_b])
    pg_session.commit()

    # Query vector: very close to Vector A
    query_vec = [0.9] * 100 + [0.0] * 2972

    results = (
        pg_session.query(Content)
        .filter(Content.embedding.isnot(None), Content.guid.in_(["art-positive", "art-negative"]))
        .order_by(Content.embedding.cosine_distance(query_vec))
        .all()
    )

    assert len(results) == 2
    assert results[0].guid == "art-positive"
    assert results[1].guid == "art-negative"


def test_content_persistence_and_pipeline_run_table(pg_session):
    """Verifies PipelineRun and User ORM models under real PostgreSQL."""
    user = User(email="test_pg@example.com", preferences=["LLMs", "Robotics"], is_active=True)
    run = PipelineRun(
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        status="success",
        articles_scraped=25,
        articles_processed=20,
        articles_embedded=20,
        digests_delivered=1,
        error_count=0,
        duration_seconds=42.8,
    )
    pg_session.add_all([user, run])
    pg_session.commit()

    saved_run = pg_session.query(PipelineRun).order_by(PipelineRun.id.desc()).first()
    assert saved_run.status == "success"
    assert saved_run.articles_scraped == 25
    assert saved_run.error_count == 0
