import os

from dotenv import load_dotenv

load_dotenv(override=True)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ainews_local.db")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.5-flash")

FROM_EMAIL = os.getenv("FROM_EMAIL")
GMAIL_TOKEN_B64 = os.getenv("GMAIL_TOKEN_B64")
ALERT_EMAIL = os.getenv("ALERT_EMAIL", FROM_EMAIL)
CRON_SECRET = os.getenv("CRON_SECRET", "")
RENDER = os.getenv("RENDER", "false").lower() in ("true", "1", "yes")

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
API_URL = os.getenv("API_URL", "http://localhost:8000")

# ── Allowed CORS Origins ──
DEFAULT_ALLOWED_ORIGINS = [
    "https://briefly-ai-newsletter.vercel.app",
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000",
]


def get_allowed_origins() -> list[str]:
    origins = list(DEFAULT_ALLOWED_ORIGINS)

    # Add FRONTEND_URL if specified
    frontend = os.getenv("FRONTEND_URL", "").strip()
    if frontend:
        origins.append(frontend)

    # Add comma-separated ALLOWED_ORIGINS if specified
    custom_origins = os.getenv("ALLOWED_ORIGINS", "").strip()
    if custom_origins:
        origins.extend([o.strip() for o in custom_origins.split(",") if o.strip()])

    # Strip trailing slashes and deduplicate while preserving order
    normalized = []
    for o in origins:
        cleaned = o.rstrip("/")
        if cleaned and cleaned not in normalized:
            normalized.append(cleaned)
    return normalized


ALLOWED_ORIGINS = get_allowed_origins()