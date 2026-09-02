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