"""In-memory and file-persisted pipeline execution state tracker for observability."""

import json
import os
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

STATE_FILE = os.path.join(os.path.dirname(__file__), "pipeline_state.json")

_server_start_time = time.time()


@dataclass
class PipelineRunStats:
    last_run_at: str | None = None
    status: str = "never_run"  # "success", "failed", "running"
    articles_scraped: int = 0
    articles_processed: int = 0
    articles_embedded: int = 0
    digests_delivered: int = 0
    errors: list[str] | None = None
    duration_seconds: float = 0.0


def get_uptime_seconds() -> int:
    """Returns the backend server uptime in seconds."""
    return int(time.time() - _server_start_time)


def load_state() -> PipelineRunStats:
    """Loads the last recorded pipeline state from file, or defaults."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                data = json.load(f)
                return PipelineRunStats(**data)
        except Exception:
            pass
    return PipelineRunStats()


def save_state(stats: PipelineRunStats) -> None:
    """Persists pipeline state to file."""
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(asdict(stats), f, indent=2)
    except Exception:
        pass


def record_pipeline_run(
    status: str,
    articles_scraped: int = 0,
    articles_processed: int = 0,
    articles_embedded: int = 0,
    digests_delivered: int = 0,
    errors: list[str] | None = None,
    duration_seconds: float = 0.0,
) -> None:
    """Records the outcome of a pipeline execution to file and database."""
    now = datetime.now(UTC)
    error_list = errors or []
    
    # 1. Update local state file
    stats = PipelineRunStats(
        last_run_at=now.isoformat(),
        status=status,
        articles_scraped=articles_scraped,
        articles_processed=articles_processed,
        articles_embedded=articles_embedded,
        digests_delivered=digests_delivered,
        errors=error_list,
        duration_seconds=round(duration_seconds, 2),
    )
    save_state(stats)

    # 2. Persist to database for surviving server restarts
    try:
        from app.database import SessionLocal
        from app.models import PipelineRun

        db = SessionLocal()
        try:
            run_entry = PipelineRun(
                started_at=now,
                finished_at=now,
                status=status,
                articles_scraped=articles_scraped,
                articles_processed=articles_processed,
                articles_embedded=articles_embedded,
                digests_delivered=digests_delivered,
                error_count=len(error_list),
                duration_seconds=round(duration_seconds, 2),
            )
            db.add(run_entry)
            db.commit()
        finally:
            db.close()
    except Exception:
        pass
