"""Semi-automated candidate question generator for Briefly.ai RAG Evaluation.

Selects representative articles from PostgreSQL across different sources, tags,
and dates, then prompts Gemini to generate candidate questions of different
difficulty types (direct, paraphrased, topic, multi_article, hard_distractor).
"""

import json
import logging
import os

from google import genai
from pydantic import BaseModel, Field

from app.config import LLM_API_KEY, LLM_MODEL
from app.database import SessionLocal
from app.models import Content, ContentStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

client = genai.Client(api_key=LLM_API_KEY)
clean_model = LLM_MODEL.replace("gemini/", "") if LLM_MODEL and "gemini/" in LLM_MODEL else LLM_MODEL

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "candidate_questions.json")


class CandidateQuestion(BaseModel):
    query: str = Field(description="The user-facing question.")
    question_type: str = Field(description="One of: 'direct', 'paraphrased', 'topic', 'hard_distractor'.")
    expected_tags: list[str] = Field(description="List of expected topic tags relevant to the question.")


class ArticleQuestions(BaseModel):
    questions: list[CandidateQuestion] = Field(description="3 to 4 varied questions testing different retrieval facets.")


def generate_candidates_for_article(article: Content) -> list[dict]:
    """Uses Gemini to generate 3-4 distinct test questions for an article."""
    summary_data = json.loads(article.summary) if article.summary else {}
    key_takeaway = summary_data.get("key_takeaway", "")
    summary_points = "\n".join(f"- {p}" for p in summary_data.get("summary_points", []))
    tags = summary_data.get("tags", [])

    prompt = f"""You are an expert AI evaluation engineer designing a benchmark dataset for a RAG system.
Given the following AI news article, generate 3 to 4 distinct test questions that a user might ask:
1. "direct": A straightforward factual question closely matching the title/topic.
2. "paraphrased": A semantic question using different wording/synonyms (tests semantic retrieval).
3. "topic": A broader conceptual query where this article provides a key answer.
4. "hard_distractor": A nuanced query testing precise technical distinction.

Article Title: {article.title}
Key Takeaway: {key_takeaway}
Summary Points:
{summary_points}
Tags: {', '.join(tags)}
"""

    try:
        response = client.models.generate_content(
            model=clean_model,
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": ArticleQuestions,
            },
        )
        data = json.loads(response.text)
        candidates = []
        for q in data.get("questions", []):
            candidates.append({
                "query": q["query"],
                "type": q["question_type"],
                "expected_articles": [
                    {
                        "guid": article.guid,
                        "url": article.url,
                        "title": article.title,
                    }
                ],
                "expected_tags": q.get("expected_tags", tags),
            })
        return candidates
    except Exception as e:
        logger.error(f"Failed to generate questions for article '{article.title}': {e}")
        return []


def generate_eval_candidates(limit: int = 10) -> None:
    """Fetches recently embedded articles and generates candidate questions for human review."""
    db = SessionLocal()
    try:
        articles = (
            db.query(Content)
            .filter(Content.status == ContentStatus.PROCESSED, Content.embedding.isnot(None))
            .order_by(Content.published_at.desc().nullslast())
            .limit(limit)
            .all()
        )

        if not articles:
            logger.warning("No embedded articles found in database.")
            return

        logger.info(f"Generating candidate questions across {len(articles)} articles...")
        all_candidates = []

        for article in articles:
            logger.info(f"Processing: '{article.title[:50]}...'")
            candidates = generate_candidates_for_article(article)
            all_candidates.extend(candidates)

        with open(OUTPUT_FILE, "w") as f:
            json.dump(all_candidates, f, indent=2)

        logger.info(f"Saved {len(all_candidates)} candidate questions to {OUTPUT_FILE}")
        logger.info("Review and curate candidates into eval_dataset.json.")

    finally:
        db.close()


if __name__ == "__main__":
    generate_eval_candidates(limit=8)
