#!/bin/bash
echo "Starting AI News FastAPI Server..."
uv run uvicorn app.api:app --host 0.0.0.0 --port 8000 &

echo "Starting AI News Background Daemon..."
uv run python -m app.main
