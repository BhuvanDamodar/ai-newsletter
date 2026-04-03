import os
from dotenv import load_dotenv

load_dotenv(override=True)
DATABASE_URL = os.getenv("DATABASE_URL")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL")

FROM_EMAIL = os.getenv("FROM_EMAIL")
GMAIL_TOKEN_B64 = os.getenv("GMAIL_TOKEN_B64")