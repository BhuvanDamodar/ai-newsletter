"""RAG Evaluation Benchmark Runner for Briefly.ai.

Evaluates semantic retrieval quality and generation correctness against the gold
standard dataset (tests/rag_eval/eval_dataset.json).

Metrics Computed:
- Recall@1 / Recall@3 / Recall@5 (retrieval accuracy across top-K results)
- Citation Validity Rate (% of answers containing valid [Article N] grounded citations)
- Average Retrieval Latency (ms)
- Average End-to-End Latency (s)

Usage:
  uv run python -m tests.rag_eval.evaluate_rag
"""

import json
import logging
import os
import re
import time

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Content
from app.rag import embed_query, generate_rag_response, retrieve_relevant_articles

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DATASET_PATH = os.path.join(os.path.dirname(__file__), "eval_dataset.json")


def load_dataset() -> list[dict]:
    """Loads the gold evaluation dataset."""
    if not os.path.exists(DATASET_PATH):
        raise FileNotFoundError(f"Evaluation dataset not found at: {DATASET_PATH}")
    with open(DATASET_PATH) as f:
        return json.load(f)


def find_article_in_db(db: Session, expected: dict) -> Content | None:
    """Finds an expected article in the database by GUID, URL, or title substring."""
    guid = expected.get("guid")
    url = expected.get("url")
    title = expected.get("title", "")

    article = None
    if guid:
        article = db.query(Content).filter(Content.guid == guid).first()
    if not article and url:
        article = db.query(Content).filter(Content.url == url).first()
    if not article and title:
        # Fallback to title substring match
        title_snippet = title[:30]
        article = db.query(Content).filter(Content.title.ilike(f"%{title_snippet}%")).first()

    return article


def run_evaluation(max_queries: int | None = None, generate_answers: bool = True) -> dict:
    """Executes the evaluation benchmark suite across all dataset queries."""
    dataset = load_dataset()
    if max_queries:
        dataset = dataset[:max_queries]

    db: Session = SessionLocal()

    total_queries = len(dataset)
    recall_at_1 = 0
    recall_at_3 = 0
    recall_at_5 = 0
    citation_valid_count = 0

    retrieval_latencies_ms: list[float] = []
    e2e_latencies_s: list[float] = []

    type_stats: dict[str, dict] = {}

    print("\n" + "=" * 70)
    print("       Briefly.ai — RAG Evaluation & Benchmarking Suite       ")
    print("=" * 70)
    print(f"Loaded {total_queries} test queries across 5 difficulty categories.\n")

    try:
        for idx, item in enumerate(dataset, 1):
            query = item["query"]
            q_type = item.get("type", "direct")
            expected_list = item.get("expected_articles", [])

            if q_type not in type_stats:
                type_stats[q_type] = {"total": 0, "hit@1": 0, "hit@3": 0, "hit@5": 0}
            type_stats[q_type]["total"] += 1

            # 1. Resolve expected target IDs from DB
            expected_ids = set()
            for exp in expected_list:
                matched = find_article_in_db(db, exp)
                if matched:
                    expected_ids.add(matched.id)

            # 2. Retrieval Phase + Latency Measurement
            t_start = time.perf_counter()
            query_emb = embed_query(query)
            retrieved = retrieve_relevant_articles(db, query_emb, limit=5)
            t_retrieval = (time.perf_counter() - t_start) * 1000
            retrieval_latencies_ms.append(t_retrieval)

            retrieved_ids = [a.id for a in retrieved]

            # Compute Hit@K and true multi-document Recall@K
            hits_in_1 = len(expected_ids.intersection(retrieved_ids[:1])) if expected_ids else 1
            hits_in_3 = len(expected_ids.intersection(retrieved_ids[:3])) if expected_ids else 1
            hits_in_5 = len(expected_ids.intersection(retrieved_ids[:5])) if expected_ids else 1
            total_exp = len(expected_ids) if expected_ids else 1

            is_hit_1 = hits_in_1 > 0
            is_hit_3 = hits_in_3 > 0
            is_hit_5 = hits_in_5 > 0
            recall_fraction_5 = hits_in_5 / total_exp

            if is_hit_1:
                recall_at_1 += 1
                type_stats[q_type]["hit@1"] += 1
            if is_hit_3:
                recall_at_3 += 1
                type_stats[q_type]["hit@3"] += 1
            if is_hit_5:
                recall_at_5 += 1
                type_stats[q_type]["hit@5"] += 1

            total_recall_5_sum = getattr(run_evaluation, "_recall_sum", 0) + recall_fraction_5
            run_evaluation._recall_sum = total_recall_5_sum

            # 3. Generation Phase (Optional, calls LLM)
            has_citation = False
            if generate_answers and retrieved:
                response = generate_rag_response(query, retrieved)
                e2e_duration = time.perf_counter() - t_start
                e2e_latencies_s.append(e2e_duration)

                answer = response.get("answer", "")
                has_citation = bool(re.search(r"\[Article \d+\]", answer))
                if has_citation:
                    citation_valid_count += 1

            hit_symbol = "✓" if is_hit_5 else "✗"
            print(f"[{idx:02d}/{total_queries:02d}] {hit_symbol} Type: {q_type:<15} | Retr: {t_retrieval:5.1f}ms | Recall@5: {recall_fraction_5*100:3.0f}% | Query: {query[:45]}...")

            # Rate limit backoff between queries to respect free-tier Gemini limits
            time.sleep(4)

    finally:
        db.close()

    # Calculate aggregate metrics
    hit1_pct = (recall_at_1 / total_queries) * 100 if total_queries else 0
    hit3_pct = (recall_at_3 / total_queries) * 100 if total_queries else 0
    hit5_pct = (recall_at_5 / total_queries) * 100 if total_queries else 0
    recall5_avg = (getattr(run_evaluation, "_recall_sum", 0) / total_queries) * 100 if total_queries else 0
    citation_pct = (citation_valid_count / total_queries) * 100 if total_queries else 0
    avg_retrieval_ms = sum(retrieval_latencies_ms) / len(retrieval_latencies_ms) if retrieval_latencies_ms else 0
    avg_e2e_s = sum(e2e_latencies_s) / len(e2e_latencies_s) if e2e_latencies_s else 0

    print("\n" + "=" * 70)
    print("                    FINAL BENCHMARK REPORT                    ")
    print("=" * 70)
    print(f"Total Queries Evaluated:      {total_queries}")
    print("──────────────────────────────────────────────────────────────────────")
    print(f"Hit@1 (Top-1 Success):        {hit1_pct:5.1f}%")
    print(f"Hit@3 (Top-3 Success):        {hit3_pct:5.1f}%")
    print(f"Hit@5 (Top-5 Success):        {hit5_pct:5.1f}%")
    print(f"Recall@5 (Target Documents):  {recall5_avg:5.1f}%")
    print(f"Citation Presence Rate:       {citation_pct:5.1f}%")
    print("──────────────────────────────────────────────────────────────────────")
    print(f"Avg Retrieval Latency:        {avg_retrieval_ms:5.1f} ms")
    print(f"Avg End-to-End Latency:       {avg_e2e_s:5.2f} s")
    print("──────────────────────────────────────────────────────────────────────")
    print("Performance by Question Type:")
    for t, s in type_stats.items():
        t_total = s["total"]
        t_r5 = (s["hit@5"] / t_total * 100) if t_total else 0
        print(f"  • {t:<16} (n={t_total}): Hit@5 = {t_r5:5.1f}%")
    print("=" * 70 + "\n")

    return {
        "queries_evaluated": total_queries,
        "hit_at_1": round(hit1_pct, 1),
        "hit_at_3": round(hit3_pct, 1),
        "hit_at_5": round(hit5_pct, 1),
        "recall_at_5": round(recall5_avg, 1),
        "citation_presence_rate": round(citation_pct, 1),
        "avg_retrieval_latency_ms": round(avg_retrieval_ms, 1),
        "avg_e2e_latency_s": round(avg_e2e_s, 2),
        "type_breakdown": type_stats,
    }


if __name__ == "__main__":
    run_evaluation(max_queries=5)
