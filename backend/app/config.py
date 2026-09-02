import os

from dotenv import load_dotenv

load_dotenv(override=True)
DATABASE_URL = os.getenv("DATABASE_URL")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL")

FROM_EMAIL = os.getenv("FROM_EMAIL")
GMAIL_TOKEN_B64 = os.getenv("GMAIL_TOKEN_B64")
ALERT_EMAIL = os.getenv("ALERT_EMAIL", FROM_EMAIL)

RENDER = os.getenv("RENDER", "false").lower() in ("true", "1", "yes")

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
API_URL = os.getenv("API_URL", "http://localhost:8000")