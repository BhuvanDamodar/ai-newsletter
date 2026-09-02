"""Tests for the embedder: text construction, inappropriate content filtering, and cutoff window."""

from datetime import UTC, datetime, timedelta

from app.embedder import build_embedding_text
from app.models import Content, ContentStatus
from tests.conftest import SAMPLE_SUMMARY


class TestBuildEmbeddingText:
    """Tests for build_embedding_text() which constructs the text to embed."""

    def test_combines_title_and_summary(self, processed_article):
        """Should combine title, key_takeaway, summary_points, and tags."""
        text = build_embedding_text(processed_article)
        
        assert "OpenAI releases new reasoning model" in text
        assert "OpenAI released a new model with improved reasoning" in text
        assert "math benchmarks" in text
        assert "OpenAI" in text  # From tags
        assert "LLMs" in text    # From tags

    def test_parts_separated_by_pipe(self, processed_article):
        """Parts should be separated by ' | '."""
        text = build_embedding_text(processed_article)
        assert " | " in text

    def test_returns_empty_for_inappropriate(self, spam_article):
        """Articles flagged as inappropriate should return empty string."""
        text = build_embedding_text(spam_article)
        assert text == ""

    def test_handles_missing_summary(self, sample_source, db_session):
        """Articles without a summary should return just the title."""
        article = Content(
            source_id=sample_source.id,
            guid="no-summary-001",
            title="Article without summary",
            url="https://example.com/no-summary",
            status=ContentStatus.PROCESSED,
        )
        db_session.add(article)
        db_session.commit()

        text = build_embedding_text(article)
        assert text == "Article without summary"

    def test_handles_malformed_json(self, sample_source, db_session):
        """Articles with invalid JSON summary should return just the title."""
        article = Content(
            source_id=sample_source.id,
            guid="bad-json-001",
            title="Article with bad JSON",
            url="https://example.com/bad-json",
            summary="this is not valid json",
            status=ContentStatus.PROCESSED,
        )
        db_session.add(article)
        db_session.commit()

        text = build_embedding_text(article)
        assert text == "Article with bad JSON"


class TestEmbeddingCutoff:
    """Tests for the 48-hour cutoff window logic."""

    def test_old_article_excluded_by_cutoff(self, sample_source, db_session):
        """Articles processed more than 48 hours ago should not be selected."""
        old_article = Content(
            source_id=sample_source.id,
            guid="old-001",
            title="Very old article",
            url="https://example.com/old",
            summary=SAMPLE_SUMMARY,
            status=ContentStatus.PROCESSED,
            processed_at=datetime.now(UTC) - timedelta(hours=72),
        )
        db_session.add(old_article)
        db_session.commit()

        cutoff = datetime.now(UTC) - timedelta(hours=48)
        recent = db_session.query(Content).filter(
            Content.status == ContentStatus.PROCESSED,
            Content.processed_at >= cutoff,
        ).all()

        assert old_article not in recent

    def test_recent_article_included(self, processed_article, db_session):
        """Articles processed within the last 48 hours should be selected."""
        cutoff = datetime.now(UTC) - timedelta(hours=48)
        recent = db_session.query(Content).filter(
            Content.status == ContentStatus.PROCESSED,
            Content.processed_at >= cutoff,
        ).all()

        assert processed_article in recent
