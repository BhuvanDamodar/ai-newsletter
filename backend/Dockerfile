FROM python:3.12-slim

# Install uv — the fast Python package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install OS dependencies needed for psycopg2 (Postgres driver)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy project definition files first (for layer caching)
COPY pyproject.toml uv.lock ./

# Install dependencies from pyproject.toml (no venv, system-wide install)
RUN uv sync --frozen --no-dev

# Copy the app source code
COPY ./app /app/app

# Allow Python to output logs without buffering
ENV PYTHONUNBUFFERED=1

CMD ["sh", "-c", "uv run uvicorn app.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
