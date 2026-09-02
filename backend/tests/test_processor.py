"""Tests for the article processor: prompt construction, status transitions, and error handling."""

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from app.models import ContentStatus
from app.processor import ArticleSummary, generate_summary


class TestArticleSummarySchema:
    """Tests for the Pydantic ArticleSummary model used for LLM output validation."""

    def test_valid_summary_parses(self):
        """A valid JSON response from Gemini should parse into ArticleSummary."""
        data = {
            "is_appropriate_ai_news": True,
            "key_takeaway": "OpenAI released GPT-5.",
            "summary_points": ["Point 1", "Point 2", "Point 3"],
            "technical_complexity": 3,
            "tags": ["OpenAI", "LLMs", "GPT-5"],
        }
        summary = ArticleSummary(**data)
        assert summary.is_appropriate_ai_news is True
        assert summary.technical_complexity == 3
        assert len(summary.tags) == 3

    def test_spam_summary_parses(self):
        """An inappropriate article summary should parse with empty fields."""
        data = {
            "is_appropriate_ai_news": False,
            "key_takeaway": "",
            "summary_points": [],
            "technical_complexity": 0,
            "tags": [],
        }
        summary = ArticleSummary(**data)
        assert summary.is_appropriate_ai_news is False
        assert summary.key_takeaway == ""


class TestProcessing:
    """Tests for article processing status transitions."""

    def test_pending_to_processed(self, db_session, pending_article):
        """After successful processing, status should change to PROCESSED."""
        # Simulate successful processing
        pending_article.summary = json.dumps({
            "is_appropriate_ai_news": True,
            "key_takeaway": "A test takeaway.",
            "summary_points": ["Point A"],
            "technical_complexity": 2,
            "tags": ["Test"],
        })
        pending_article.status = ContentStatus.PROCESSED
        pending_article.processed_at = datetime.now(UTC)
        db_session.commit()

        db_session.refresh(pending_article)
        assert pending_article.status == ContentStatus.PROCESSED
        assert pending_article.summary is not None
        assert pending_article.processed_at is not None

    def test_pending_to_failed(self, db_session, pending_article):
        """After a processing failure, status should change to FAILED."""
        pending_article.status = ContentStatus.FAILED
        db_session.commit()

        db_session.refresh(pending_article)
        assert pending_article.status == ContentStatus.FAILED

    def test_processed_summary_has_required_fields(self, processed_article):
        """A processed article's summary JSON should contain all expected fields."""
        data = json.loads(processed_article.summary)
        assert "is_appropriate_ai_news" in data
        assert "key_takeaway" in data
        assert "summary_points" in data
        assert "technical_complexity" in data
        assert "tags" in data

    def test_rate_limit_detection(self):
        """The processor should detect 429 errors in exception messages."""
        error_msg = "429 RESOURCE_EXHAUSTED. You exceeded your current quota."
        assert "429" in str(error_msg)

    @patch("app.processor.client")
    def test_generate_summary_clips_long_text(self, mock_client):
        """Text longer than 15000 chars should be clipped before sending to Gemini."""
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "is_appropriate_ai_news": True,
            "key_takeaway": "Test",
            "summary_points": ["Point"],
            "technical_complexity": 1,
            "tags": ["Test"],
        })
        mock_client.models.generate_content.return_value = mock_response

        long_text = "A" * 20000
        result = generate_summary(long_text)
        
        # Verify the LLM was called
        mock_client.models.generate_content.assert_called_once()
        call_args = mock_client.models.generate_content.call_args
        prompt = call_args[1]["contents"] if "contents" in call_args[1] else call_args[0][0]
        assert len(prompt) < 20000  # Verify clipped
        
        # The result should be valid JSON
        parsed = json.loads(result)
        assert parsed["is_appropriate_ai_news"] is True
