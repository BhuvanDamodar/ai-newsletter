"""Tests for the RAG module: context building, response formatting, and mocked retrieval."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from app.models import Content, ContentStatus
from app.rag import build_rag_context, generate_rag_response


class TestBuildRagContext:
    """Tests for build_rag_context() which formats retrieved articles for the LLM prompt."""

    def test_formats_single_article(self, processed_article):
        """A single article should produce a context string with Article 1 header."""
        context = build_rag_context([processed_article])
        assert "[Article 1]" in context
        assert processed_article.title in context
        assert processed_article.url in context

    def test_includes_key_takeaway(self, processed_article):
        """The context should include the key takeaway from the article summary."""
        context = build_rag_context([processed_article])
        assert "Key Takeaway:" in context
        assert "improved reasoning capabilities" in context

    def test_includes_summary_points(self, processed_article):
        """The context should include bullet points from the summary."""
        context = build_rag_context([processed_article])
        assert "math benchmarks" in context

    def test_multiple_articles_numbered(self, multiple_articles):
        """Multiple articles should be numbered sequentially."""
        context = build_rag_context(multiple_articles[:3])
        assert "[Article 1]" in context
        assert "[Article 2]" in context
        assert "[Article 3]" in context

    def test_articles_separated_by_divider(self, multiple_articles):
        """Articles should be separated by '---' dividers."""
        context = build_rag_context(multiple_articles[:2])
        assert "---" in context

    def test_handles_no_summary(self, sample_source, db_session):
        """Articles without a summary should show 'No summary available'."""
        article = Content(
            source_id=sample_source.id,
            guid="no-summary-rag",
            title="Article without summary",
            url="https://example.com/no-summary",
            status=ContentStatus.PROCESSED,
            published_at=datetime.now(UTC),
        )
        db_session.add(article)
        db_session.commit()

        context = build_rag_context([article])
        assert "[Article 1]" in context
        assert "Article without summary" in context


class TestGenerateRagResponse:
    """Tests for generate_rag_response() with mocked Gemini."""

    def test_empty_articles_returns_fallback(self):
        """When no articles are retrieved, a helpful fallback message should be returned."""
        result = generate_rag_response("What is AI?", [])
        assert "couldn't find any relevant articles" in result["answer"]
        assert result["sources"] == []

    @patch("app.rag.client")
    def test_response_includes_sources(self, mock_client, multiple_articles):
        """The response should include source metadata for all retrieved articles."""
        mock_response = MagicMock()
        mock_response.text = "Based on recent news [Article 1], OpenAI has..."
        mock_client.models.generate_content.return_value = mock_response

        articles = multiple_articles[:3]
        result = generate_rag_response("What is OpenAI doing?", articles)

        assert len(result["sources"]) == 3
        assert result["sources"][0]["title"] == articles[0].title
        assert result["sources"][0]["url"] == articles[0].url
        assert "tags" in result["sources"][0]

    @patch("app.rag.client")
    def test_response_answer_comes_from_gemini(self, mock_client, processed_article):
        """The answer should be the text returned by Gemini."""
        mock_response = MagicMock()
        mock_response.text = "OpenAI released a new reasoning model [Article 1]."
        mock_client.models.generate_content.return_value = mock_response

        result = generate_rag_response("Tell me about OpenAI", [processed_article])
        assert result["answer"] == "OpenAI released a new reasoning model [Article 1]."

    @patch("app.rag.client")
    def test_source_metadata_includes_key_takeaway(self, mock_client, processed_article):
        """Source metadata should include key_takeaway extracted from the article summary."""
        mock_response = MagicMock()
        mock_response.text = "Answer text"
        mock_client.models.generate_content.return_value = mock_response

        result = generate_rag_response("Query", [processed_article])
        assert result["sources"][0]["key_takeaway"] == "OpenAI released a new model with improved reasoning capabilities."
