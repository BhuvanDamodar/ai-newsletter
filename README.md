<!-- <p align="center">
  <img src="docs/logo.png" alt="Briefly.ai Logo" width="100" />
</p> -->

<h1 align="center">Briefly.ai</h1>

<p align="center">
  <strong>An automated AI news intelligence platform with personalized daily digests, an interactive discovery dashboard, and conversational RAG search.</strong>
</p>

<p align="center">
  <a href="#architecture">Architecture</a> •
  <a href="#features">Features</a> •
  <a href="#tech-stack">Tech Stack</a> •
  <a href="#getting-started">Getting Started</a> •
  <a href="#api-reference">API Reference</a> •
  <a href="#deployment">Deployment</a>
</p>

---

## Overview

Briefly.ai is a full-stack Generative AI application that automatically ingests news from 8+ curated AI sources, summarizes and analyzes each article with Google Gemini, scores content against user preferences, generates high-dimensional vector embeddings in PostgreSQL (`pgvector`), and serves both personalized daily digests and an interactive web platform.

Users can:
1. **Subscribe to Daily Digests** — Receive a personalized email digest every morning tailored to their interests (LLMs, AI Ethics, Hardware, Startups, etc.).
2. **Explore the News Dashboard** (`/dashboard`) — Browse, search, and filter all curated AI news by source, topic tags, date range, and technical complexity.
3. **Chat with Your News** (`/chat`) — Query the article archive using Retrieval-Augmented Generation (RAG). Gemini answers questions grounded strictly in retrieved news articles, citing sources with direct links.

> **Live Deployments:**
> - **Frontend (Vercel):** [`briefly-ai-newsletter.vercel.app`](https://briefly-ai-newsletter.vercel.app/)
> - **Backend API (Render):** [`ai-newsletter-ejym.onrender.com`](https://ai-newsletter-ejym.onrender.com)
> - **Database (Neon):** Serverless PostgreSQL 17 with `pgvector`
> - **Automation (GitHub Actions):** Daily trigger at 5:00 AM UTC (7:00 AM CET)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              SYSTEM ARCHITECTURE                            │
│                                                                             │
│   ┌──────────────┐    5:00 AM UTC      ┌─────────────────────────────────┐  │
│   │ GitHub       │    (7:00 AM CET)    │   FastAPI Backend (Render)      │  │
│   │ Actions      │ ──────────────────► │                                 │  │
│   │ (Cron)       │  /api/cron/trigger  │  ┌───────────────────────────┐  │  │
│   └──────────────┘                     │  │     Pipeline (BG Task)    │  │  │
│                                        │  │                           │  │  │
│                                        │  │ 1. Scrape   ─► RSS ×8     │  │  │
│                                        │  │ 2. Process  ─► Gemini 2.5 │  │  │
│                                        │  │ 2.5. Embed  ─► pgvector   │  │  │
│                                        │  │ 3. Curate   ─► Score      │  │  │
│                                        │  │ 4. Deliver  ─► Gmail API  │  │  │
│                                        │  └─────────────┬─────────────┘  │  │
│                                        │                │                │  │
│                                        │  ┌─────────────▼─────────────┐  │  │
│   ┌──────────────┐                     │  │    RAG Engine (rag.py)    │  │  │
│   │ Next.js      │ ◄── Search/Chat ──► │  │    Query Embed ─► Cosine  │  │  │
│   │ App Router   │     /api/articles   │  │    Search ─► Grounded Gen │  │  │
│   │ (Vercel)     │     /api/chat       │  └─────────────┬─────────────┘  │  │
│   └──────────────┘                     └────────────────┼────────────────┘  │
│                                                         │                   │
│                                              ┌──────────▼──────────┐        │
│                                              │   Neon PostgreSQL   │        │
│                                              │   + pgvector (3072) │        │
│                                              └─────────────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Pipeline Stages

| Stage | Module | Description |
|-------|--------|-------------|
| **1. Scrape** | `scraper/orchestrator.py` | Seeds default sources on first run, then dispatches the RSS scraper module. |
| **2. Parse** | `scraper/rss_scraper.py` | Fetches RSS feeds from 8 sources, deduplicates by GUID, and inserts new articles as `PENDING_PROCESSING`. |
| **3. Summarize** | `processor.py` | Evaluates articles via **Google Gemini 2.5 Flash** with a Pydantic schema (`ArticleSummary`). Generates single-sentence key takeaway, bullet points, tags, complexity score (1–5), and an appropriateness filter. Uses `tenacity` exponential backoff for rate limits. |
| **3.5. Embed** | `embedder.py` | Combines `title \| takeaway \| points \| tags` into semantic text, generates **3072-dimensional dense vectors** with `gemini-embedding-001`, and stores them in PostgreSQL via `pgvector`. Employs a 48-hour rolling window to avoid re-embedding historical records. |
| **4. Curate** | `curator.py` | Scores processed articles against user preference keywords. Checks `DigestLog` to ensure cross-day deduplication (no user receives the same article twice). Picks top 5 articles per user. |
| **5. Deliver** | `email_service.py` | Renders personalized HTML digests using Jinja2 templates (`digest.html`), delivering via **Gmail REST API** with base64 OAuth2 refresh tokens. Also handles welcome emails. |
| **6. RAG Engine** | `rag.py` | Embeds user queries, executes vector cosine distance search (`<=>`) against embedded articles, formats retrieved context, and prompts Gemini to produce grounded answers citing `[Article N]`. |

### Data Model

```
┌──────────┐       ┌────────────────────────┐       ┌────────────┐
│  Source   │ 1───* │        Content         │ *───* │ DigestLog  │
│  ──────   │       │        ───────         │       │ ─────────  │
│  name     │       │  title                 │       │ user_id    │
│  url_or_id│       │  summary (JSON)        │       │ content_id │
│  type:RSS │       │  status                │       │ sent_at    │
│  is_active│       │  raw_content           │       └────────────┘
└──────────┘       │  published_at          │              │
                    │  embedding (vector:3072│       ┌──────┴─────┐
                    └────────────────────────┘       │    User    │
                                                     │    ────    │
                                                     │ email      │
                                                     │ preferences│
                                                     │ is_active  │
                                                     └────────────┘
```

---

## Features

### Core Intelligence & Pipeline (Phases 1 & 2)
- **8 Curated RSS Sources** — TechCrunch AI, OpenAI Blog, Anthropic News, Reddit r/Artificial, Reddit r/MachineLearning, Google DeepMind, Hugging Face Blog, MIT Technology Review.
- **LLM-Powered Summaries** — Structured JSON output verified by Pydantic (key takeaway, bullet points, tags, complexity score).
- **Automated Content Moderation** — Flags spam, vulgarity, and non-AI submissions, dropping them from digests and chat.
- **Personalized Daily Delivery** — Keyword scoring matches user interests, deduplicated against `DigestLog`.
- **Gmail REST API Integration** — Reliable OAuth2 token delivery that avoids cloud SMTP port blocks.
- **Automated Cron Scheduling** — GitHub Actions triggers the pipeline every morning; APScheduler runs locally.

### Interactive Web Platform & RAG (Phase 3)
- **Glassmorphic Navigation Bar** — Universal navbar providing instant switching between Landing (`/`), Dashboard (`/dashboard`), and Chat (`/chat`).
- **News Dashboard (`/dashboard`)**:
  - Live statistics cards: Total Articles, Articles Today, Active Sources, Subscriber Count.
  - Live search across titles.
  - Multi-filter drawer: Filter by Source, Topic Tag (with frequency counts), and Time Range (Today, 7 days, 30 days, 90 days, All time).
  - Article cards with technical complexity gauges (Beginner to Expert), key takeaways, tags, and direct source links.
  - Full client-side and server-side pagination.
- **Conversational RAG Chat (`/chat`)**:
  - Semantic Q&A over the entire news database using **Gemini Embedding (3072 dimensions)** and **pgvector**.
  - 6 suggested discovery prompts for immediate interaction.
  - Grounded responses with source citation badges `[Article N]`.
  - Interactive source reference cards showing article titles, dates, takeaways, tags, and external URLs.

---

## Tech Stack

| Layer | Technologies |
|-------|--------------|
| **Frontend** | Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS v4, Framer Motion, Lucide Icons |
| **Backend API** | Python 3.12, FastAPI, Uvicorn, SQLAlchemy ORM, Pydantic, Tenacity |
| **AI / LLM** | Google Gemini API (`gemini-2.5-flash`), Gemini Embedding API (`gemini-embedding-001`) |
| **Vector Database** | PostgreSQL 17 + `pgvector` extension (Docker `pgvector/pgvector:pg17` local / Neon cloud) |
| **Scraping & Data** | `feedparser`, `beautifulsoup4`, `requests`, `python-dateutil` |
| **Email Delivery** | Gmail REST API (`google-api-python-client`), Jinja2 HTML templates |
| **Automation** | GitHub Actions Cron (production), APScheduler (local daemon) |
| **DevOps & Infra** | Docker, Docker Compose, Render (Web Service), Vercel (Frontend), Neon (Postgres) |

---

## Project Structure

```
ai-news/
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml              # Dependencies (managed with uv)
│   ├── get_gmail_token.py          # Gmail OAuth2 desktop token helper
│   └── app/
│       ├── main.py                 # Pipeline scheduler & worker daemon
│       ├── api.py                  # FastAPI endpoints (REST + RAG + Dashboard)
│       ├── config.py               # Environment configuration
│       ├── database.py             # SQLAlchemy session & pgvector extension init
│       ├── models.py               # ORM Models (User, Source, Content with Vector, DigestLog)
│       ├── processor.py            # Gemini summarization & Pydantic validation
│       ├── embedder.py             # Batch vector embedding generator (gemini-embedding-001)
│       ├── rag.py                  # Full RAG chain (embed query -> cosine search -> answer)
│       ├── curator.py              # Preference scoring & deduplication
│       ├── email_service.py        # Gmail API delivery & Jinja2 rendering
│       ├── scraper/
│       │   ├── orchestrator.py     # Source seeding & runner dispatch
│       │   └── rss_scraper.py      # RSS feed fetching and parsing
│       └── templates/
│           ├── digest.html         # Daily digest email template
│           └── welcome.html        # Welcome email template
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   └── src/app/
│       ├── layout.tsx              # Root HTML & metadata layout
│       ├── globals.css             # Glassmorphism tokens & Tailwind styling
│       ├── page.tsx                # Landing page with topic picker & subscription form
│       ├── components/
│       │   └── Navbar.tsx          # Shared sticky navigation bar
│       ├── dashboard/
│       │   └── page.tsx            # News dashboard with search, filters & stats
│       ├── chat/
│       │   └── page.tsx            # Conversational RAG chat interface
│       └── unsubscribe/
│           └── page.tsx            # Unsubscribe confirmation screen
├── .github/
│   └── workflows/
│       └── daily_pipeline.yml      # Scheduled cron triggering Render wake & pipeline
├── docker-compose.yml              # Local multi-service orchestration (DB, API, Worker, UI)
├── README.md
└── .env                            # Environment variables (git-ignored)
```

---

## Getting Started

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [Google Gemini API Key](https://aistudio.google.com/apikey)
- *(Optional)* Gmail OAuth2 credentials for email delivery

### 1. Clone & Configure

```bash
git clone https://github.com/BhuvanDamodar/briefly.ai-Newsletter.git
cd briefly.ai-Newsletter
```

Create a `.env` file in the project root:

```env
# ── Database (Postgres with pgvector) ──
POSTGRES_USER=ainews_user
POSTGRES_PASSWORD=ainews_password
POSTGRES_DB=ainews
DATABASE_URL=postgresql://ainews_user:ainews_password@db:5432/ainews

# ── Gemini LLM & Embeddings ──
LLM_API_KEY=your_gemini_api_key
LLM_MODEL=gemini-2.5-flash

# ── Email Delivery (Optional) ──
FROM_EMAIL=your_email@gmail.com
GMAIL_TOKEN_B64=your_base64_oauth_token

# ── Frontend & API URLs ──
FRONTEND_URL=http://localhost:3000
API_URL=http://localhost:8000
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 2. Start Services via Docker Compose

```bash
docker-compose up --build
```

This starts all four services:
- **`db`** (`5432`): `pgvector/pgvector:pg17`
- **`api`** (`8000`): FastAPI server
- **`worker`**: Background APScheduler worker
- **`frontend`** (`3000`): Next.js web application

### 3. Open the Application

- **Landing Page:** [http://localhost:3000](http://localhost:3000)
- **News Dashboard:** [http://localhost:3000/dashboard](http://localhost:3000/dashboard)
- **RAG Chat:** [http://localhost:3000/chat](http://localhost:3000/chat)
- **Interactive API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)

---

## API Reference

### Core Pipeline & Subscription
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | API status check |
| `GET` | `/api/health` | Lightweight stateless health check for speculative frontend pre-warming |
| `GET` | `/api/status` | Comprehensive observability status: uptime, database connection, article/user counts, and last pipeline run details |
| `GET` | `/api/cron/trigger` | Triggers the ingestion, processing, embedding, and delivery pipeline |
| `POST` | `/api/subscribe` | Subscribes an email with selected topic keywords |
| `GET` | `/api/preferences/{email}` | Fetches stored preferences for an email |
| `GET` | `/api/unsubscribe?email=...` | Deactivates a user's subscription |

### Dashboard & RAG Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/articles` | Paginated article list supporting `page`, `page_size`, `search`, `source`, `tag`, and `days` filters |
| `GET` | `/api/articles/stats` | Aggregated counts for total articles, today's articles, active sources, and subscribers |
| `GET` | `/api/articles/sources` | Returns active RSS source names for filter selectors |
| `GET` | `/api/articles/tags` | Extracted and sorted topic tag frequency counts |
| `POST` | `/api/chat` | RAG query endpoint (`{ "query": "..." }`) returning grounded answer and source citations |

---

## Testing & Quality Assurance

Briefly.ai employs a multi-tiered testing strategy combining fast local SQLite emulation with real PostgreSQL + pgvector integration testing:

1. **Fast Unit & Integration Suite (SQLite)**: Compiles `Vector(3072)` as SQLite `TEXT` via `@compiles(Vector, "sqlite")`, running 47 tests completely offline in ~1.5 seconds.
2. **Real Database Integration Suite (PostgreSQL + pgvector)**: Runs against a live `pgvector/pgvector:pg17` instance (in CI or Docker) in [`test_pgvector_integration.py`](file:///Users/bhuvandamodar/Documents/Projects/ai-news/backend/tests/test_pgvector_integration.py) to verify vector insertion, 3072-dimension constraints, cosine distance (`<=>`) queries, and nearest-neighbor ranking.

### Running Tests Locally

```bash
cd backend
# Run unit tests
uv run pytest tests/ -v

# Run linter
uv run ruff check .
```

### Test Suite Structure

| Test Module | Coverage Area |
|---|---|
| [`test_curator.py`](file:///Users/bhuvandamodar/Documents/Projects/ai-news/backend/tests/test_curator.py) | User preference scoring algorithms (+5 per topic match, +1 base), spam filtering (`is_appropriate_ai_news`), top-N selection, and `DigestLog` deduplication. |
| [`test_processor.py`](file:///Users/bhuvandamodar/Documents/Projects/ai-news/backend/tests/test_processor.py) | Pydantic schema validation, LLM prompt formatting, state transitions (`PENDING` $\to$ `PROCESSED` / `FAILED`), text clipping (>15k characters), and 429 rate limit backoff. |
| [`test_embedder.py`](file:///Users/bhuvandamodar/Documents/Projects/ai-news/backend/tests/test_embedder.py) | Text construction (`title \| takeaway \| points \| tags`), pipe-separated formatting, 48-hour cutoff window filter. |
| [`test_rag.py`](file:///Users/bhuvandamodar/Documents/Projects/ai-news/backend/tests/test_rag.py) | Context builder numbering `[Article N]`, section dividers, fallback on empty article list, and grounded generation with source citations. |
| [`test_api.py`](file:///Users/bhuvandamodar/Documents/Projects/ai-news/backend/tests/test_api.py) | Full FastAPI endpoint integration tests: `/api/health`, `/api/status`, `/api/subscribe`, preference fetching, unsubscription, article pagination, search filters, stats aggregation, and `/api/chat`. |
| [`test_pgvector_integration.py`](file:///Users/bhuvandamodar/Documents/Projects/ai-news/backend/tests/test_pgvector_integration.py) | Live PostgreSQL tests: pgvector extension check, 3072-d insertion, dimension mismatch rejection, cosine distance ranking, and `PipelineRun` table persistence. |

---

## Continuous Integration (CI/CD)

Automated continuous integration is handled by **GitHub Actions** ([`.github/workflows/ci.yml`](file:///Users/bhuvandamodar/Documents/Projects/ai-news/.github/workflows/ci.yml)) on every push and pull request:

```
Push / PR ──► ┌────────────────────────────────────────────────────────┐
              │ 1. backend-test: Python 3.12 (uv) + pgvector:pg17      │
              │    • ruff check . (Code linting)                       │
              │    • pytest tests/ -v (Unit + PostgreSQL tests)        │
              │    • docker build backend (Production container check) │
              ├────────────────────────────────────────────────────────┤
              │ 2. frontend-build: Node.js 20                          │
              │    • npm ci                                            │
              │    • npm run build (Next.js 16 typecheck & bundle)     │
              └────────────────────────────────────────────────────────┘
```

---

## Observability & Error Alerting

- **Structured JSON Logging:** Automatically enabled in production (`RENDER=true`). Outputs single-line JSON records formatted for cloud log aggregators.
- **Pipeline Health & Telemetry (`/api/status`):** Queries persisted `PipelineRun` records from PostgreSQL to survive server restarts, tracking execution status, article counts, duration, and error counts without exposing internal stack traces.
- **Automated Failure Alerts:** If an unhandled exception occurs during the daily pipeline run, an operational failure report with stack traces and timestamps is automatically dispatched to `ALERT_EMAIL` via the authenticated Gmail API.

---

## RAG Evaluation Benchmark Suite

A standalone benchmarking suite evaluates semantic retrieval quality and citation accuracy:

- **Dataset (`eval_dataset.json`):** 20 curated test queries across 5 question types (`direct`, `paraphrased`, `topic`, `multi_article`, and `hard_distractor`) referencing immutable article GUIDs and URLs.
- **Benchmark Runner (`evaluate_rag.py`):** Computes **Hit@1**, **Hit@3**, **Hit@5**, **Recall@5** (multi-document target coverage), **Citation Presence Rate**, and retrieval/end-to-end latency.

```bash
cd backend
uv run python -m tests.rag_eval.evaluate_rag
```

---

## Cold-Start & Performance Architecture

Briefly.ai is built to run on $0/month free-tier infrastructure (Render web services auto-sleep after 15 minutes). The frontend is engineered to degrade gracefully and minimize cold-start friction:

1. **Speculative Pre-Warming (`Navbar.tsx`):** A non-blocking health check ping (`GET /api/health`) fires once per session on initial interaction, allowing Render to boot up while the user browses.
2. **Client-Side Session Cache with Background Refresh (`dashboard/page.tsx`):** Articles, stats, sources, and tags render immediately from client-side session cache without waiting for the backend, followed by a background revalidation.
3. **Confirmed Subscription & Unsubscription (`page.tsx`, `unsubscribe/page.tsx`):** Uses confirmed persistence and bounded retries to handle transient failures and backend cold starts, providing informative progress feedback (*"Connecting to service..."*).
4. **Progressive Chat UX (`chat/page.tsx`):** Multi-stage loading indicators inform the user of progress during cold-start RAG queries.

---

## Deployment

The application is deployed across managed cloud providers on $0/month free tiers:

| Component | Provider | Notes |
|-----------|----------|-------|
| **Backend API** | [Render](https://render.com) | Free Web Service with auto-sleep |
| **Vector Database** | [Neon](https://neon.tech) | Free PostgreSQL with native `pgvector` |
| **Frontend** | [Vercel](https://vercel.com) | Next.js deployment on Hobby tier |
| **Scheduler** | [GitHub Actions](https://github.com/features/actions) | Daily cron wakes Render and triggers pipeline |
| **LLM & Vectors** | [Google Gemini](https://ai.google.dev) | Gemini 2.5 Flash + Embedding 001 free tier |
| **Email** | Gmail REST API | 500 emails/day free tier quota |

> **Production Database Setup Note**:
> When deploying to Neon PostgreSQL, ensure the extension and column are initialized:
> ```sql
> CREATE EXTENSION IF NOT EXISTS vector;
> ALTER TABLE content ADD COLUMN IF NOT EXISTS embedding vector(3072);
> ```

