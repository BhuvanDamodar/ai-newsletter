import json
import logging
from google import genai
from sqlalchemy.orm import Session
from tenacity import retry, wait_exponential, stop_after_attempt

from app.database import SessionLocal
from app.models import Content, ContentStatus
from app.config import LLM_API_KEY, LLM_MODEL

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "gemini-embedding-001"
client = genai.Client(api_key=LLM_API_KEY)
clean_model = LLM_MODEL.replace("gemini/", "") if LLM_MODEL and "gemini/" in LLM_MODEL else LLM_MODEL


@retry(wait=wait_exponential(multiplier=1, min=10, max=60), stop=stop_after_attempt(3), reraise=True)
def embed_query(text: str) -> list[float]:
    """Generates an embedding vector for a user's chat query."""
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
    )
    return result.embeddings[0].values


def retrieve_relevant_articles(db: Session, query_embedding: list[float], limit: int = 5) -> list[Content]:
    """
    Finds the most semantically similar articles using pgvector cosine distance.
    Only searches articles that have been processed and embedded.
    """
    articles = (
        db.query(Content)
        .filter(
            Content.status == ContentStatus.PROCESSED,
            Content.embedding.isnot(None),
        )
        .order_by(Content.embedding.cosine_distance(query_embedding))
        .limit(limit)
        .all()
    )
    return articles


def build_rag_context(articles: list[Content]) -> str:
    """Formats retrieved articles into a context string for the LLM."""
    context_parts = []
    
    for i, article in enumerate(articles, 1):
        summary_text = ""
        if article.summary:
            try:
                summary_data = json.loads(article.summary)
                key_takeaway = summary_data.get("key_takeaway", "")
                points = summary_data.get("summary_points", [])
                summary_text = f"Key Takeaway: {key_takeaway}\n"
                summary_text += "\n".join(f"  - {p}" for p in points)
            except json.JSONDecodeError:
                summary_text = "No summary available."
        
        context_parts.append(
            f"[Article {i}] \"{article.title}\"\n"
            f"Source URL: {article.url}\n"
            f"Published: {article.published_at.strftime('%Y-%m-%d') if article.published_at else 'Unknown'}\n"
            f"{summary_text}\n"
        )
    
    return "\n---\n".join(context_parts)


@retry(wait=wait_exponential(multiplier=1, min=10, max=60), stop=stop_after_attempt(3), reraise=True)
def generate_rag_response(query: str, articles: list[Content]) -> dict:
    """
    Generates a grounded answer to the user's query using retrieved article context.
    Returns { "answer": str, "sources": list[dict] }.
    """
    if not articles:
        return {
            "answer": "I couldn't find any relevant articles in the database to answer your question. Try asking about a specific AI topic that's been in the news recently.",
            "sources": []
        }
    
    context = build_rag_context(articles)
    
    prompt = f"""You are an expert AI news analyst for Briefly.ai. A user is asking a question about recent AI news.

Answer their question based ONLY on the following news articles retrieved from our database. Be concise, accurate, and informative.

IMPORTANT RULES:
1. Only use information from the provided articles. Do not make up facts.
2. When referencing information, cite the article number in brackets, e.g. [Article 1].
3. If the articles don't contain enough information to fully answer the question, say so honestly.
4. Keep your response concise but comprehensive.

--- RETRIEVED ARTICLES ---
{context}
--- END ARTICLES ---

User's Question: {query}

Answer:"""

    response = client.models.generate_content(
        model=clean_model,
        contents=prompt,
    )
    
    # Build source references
    sources = []
    for article in articles:
        summary_data = {}
        if article.summary:
            try:
                summary_data = json.loads(article.summary)
            except json.JSONDecodeError:
                pass
        
        sources.append({
            "id": article.id,
            "title": article.title,
            "url": article.url,
            "published_at": article.published_at.isoformat() if article.published_at else None,
            "key_takeaway": summary_data.get("key_takeaway", ""),
            "tags": summary_data.get("tags", []),
        })
    
    return {
        "answer": response.text,
        "sources": sources,
    }


def chat(query: str) -> dict:
    """
    Full RAG pipeline: embed query → retrieve articles → generate response.
    This is the main entry point called by the API endpoint.
    """
    logger.info(f"RAG Chat query: '{query[:80]}...'")
    
    db = SessionLocal()
    try:
        # 1. Embed the user's query
        query_embedding = embed_query(query)
        
        # 2. Retrieve relevant articles
        articles = retrieve_relevant_articles(db, query_embedding, limit=5)
        logger.info(f"Retrieved {len(articles)} relevant articles")
        
        # 3. Generate grounded response
        result = generate_rag_response(query, articles)
        
        return result
        
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = chat("What are the latest developments in LLMs?")
    print(f"\nAnswer: {result['answer']}")
    print(f"\nSources: {[s['title'] for s in result['sources']]}")
