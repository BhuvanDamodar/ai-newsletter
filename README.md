<!-- <p align="center">
  <img src="docs/logo.png" alt="Briefly.ai Logo" width="100" />
</p> -->

<h1 align="center">Briefly.ai</h1>

<p align="center">
  <strong>An AI-powered news curation pipeline that delivers personalized daily digests straight to your inbox.</strong>
</p>

<p align="center">
  <a href="#architecture">Architecture</a> •
  <a href="#features">Features</a> •
  <a href="#tech-stack">Tech Stack</a> •
  <a href="#getting-started">Getting Started</a> •
  <a href="#deployment">Deployment</a> •
  <a href="#api-reference">API Reference</a>
</p>

---

## Overview

Briefly.ai is a full-stack application that automatically scrapes AI news from 8+ curated sources, summarizes each article using Google Gemini, scores content against individual user preferences, and delivers a beautifully formatted HTML email digest every morning - completely hands-free.

Users subscribe through a sleek Next.js landing page, select their interests (LLMs, AI Ethics, Hardware, etc.), and receive a daily email containing only the articles most relevant to them.

> **Live:** The landing page is at [`briefly-ai-newsletter.vercel.app`](https://briefly-ai-newsletter.vercel.app/), the backend API runs at [`ai-newsletter-ejym.onrender.com`](https://ai-newsletter-ejym.onrender.com), and the daily pipeline is triggered automatically via GitHub Actions every morning at 7:00 AM CET.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PRODUCTION FLOW                              │
│                                                                     │
│  ┌──────────────┐   5:00 AM UTC    ┌─────────────────────────────┐  │
│  │ GitHub       │   (7:00 AM CET)  │   FastAPI (Render)          │  │
│  │ Actions      │ ──────────────►  │                             │  │
│  │ (Cron)       │  /api/cron/trigger│                             │  │
│  └──────────────┘                  │  ┌───────────────────────┐  │  │
│                                     │  │   Pipeline (BGTask)   │  │  │
│                                     │  │                       │  │  │
│                                     │  │  1. Scrape  ─► RSS ×8 │  │  │
│                                     │  │  2. Process ─► Gemini │  │  │
│                                     │  │  3. Curate  ─► Score  │  │  │
│                                     │  │  4. Deliver ─► Gmail  │  │  │
│                                     │  └───────────────────────┘  │  │
│                                     └──────────┬──────────────────┘  │
│                                                │                     │
│  ┌──────────────┐                    ┌─────────▼─────────┐          │
│  │ Next.js      │◄── Subscribe ────► │   Neon PostgreSQL  │          │
│  │ (Vercel)     │    /api/subscribe  │   (Cloud DB)       │          │
│  └──────────────┘                    └───────────────────┘          │
└─────────────────────────────────────────────────────────────────────┘
```

### Pipeline Stages

| Stage | Module | Description |
|-------|--------|-------------|
| **1. Scrape** | `scraper/orchestrator.py` | Seeds default sources on first run, then dispatches the RSS scraper module. |
| **2. Parse** | `scraper/rss_scraper.py` | Fetches RSS feeds from 8 sources, filters to the last 24 hours, deduplicates by GUID, and stores raw content. |
| **3. Process** | `processor.py` | Sends each article to **Google Gemini** with a structured Pydantic schema. Returns key takeaway, bullet summary, tags, technical complexity score, and a content-appropriateness flag to filter spam/vulgarity. Uses `tenacity` for automatic retry with exponential backoff on rate limits. |
| **4. Curate** | `curator.py` | Scores every processed article against each user's preference keywords. Deduplicates against `DigestLog` so users never see the same article twice. Returns the top 5 articles per user, ranked by relevance. |
| **5. Deliver** | `email_service.py` | Renders a personalized HTML email using Jinja2 templates (`digest.html`), then sends it via the **Gmail REST API** (OAuth2 credentials encoded as base64). Also handles welcome emails for new subscribers. |

### Data Model

```
┌──────────┐       ┌───────────┐       ┌────────────┐
│  Source   │ 1───* │  Content   │ *───* │ DigestLog  │
│  ──────   │       │  ───────   │       │ ─────────  │
│  name     │       │  title     │       │ user_id    │
│  url_or_id│       │  summary   │       │ content_id │
│  type:RSS │       │  status    │       │ sent_at    │
└──────────┘       │  raw_content│       └────────────┘
                    │  published_at│              │
                    └───────────┘          ┌─────┴──────┐
                                           │   User     │
                                           │   ────     │
                                           │   email    │
                                           │ preferences│
                                           │  is_active │
                                           └────────────┘
```

---

## Features

- **8 Built-in RSS Sources** - TechCrunch AI, OpenAI Blog, Anthropic News, Reddit r/Artificial, Reddit r/MachineLearning, Google DeepMind, Hugging Face, MIT Technology Review
- **LLM-Powered Summaries** - Structured JSON output validated by Pydantic (key takeaway, bullet points, tags, complexity score)
- **Content Moderation** - Gemini flags spam, vulgarity, and off-topic posts, which are automatically excluded from digests
- **Personalized Curation** - Keyword-based relevance scoring with deduplication across days
- **Gmail REST API Delivery** - Bypasses cloud provider SMTP firewalls using native OAuth2 token authentication
- **Automated Scheduling** - GitHub Actions triggers the pipeline daily; APScheduler available for local development
- **Welcome Emails** - New subscribers receive a styled welcome email upon signup
- **Unsubscribe Support** - One-click unsubscribe link in every email footer with a dedicated unsubscribe page
- **Glassmorphism UI** - Premium dark-mode landing page with Framer Motion animations
- **Render Cold-Start Handling** - GitHub Actions workflow wakes the free-tier server before triggering the pipeline

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js 15, React, TypeScript, Tailwind CSS, Framer Motion, Lucide Icons |
| **Backend API** | FastAPI, Uvicorn, SQLAlchemy, Pydantic |
| **AI/LLM** | Google Gemini (`google-genai` SDK), Pydantic structured output |
| **Scraping** | `feedparser`, `requests`, `BeautifulSoup4`, `python-dateutil` |
| **Email** | Gmail REST API (`google-api-python-client`), Jinja2 HTML templates |
| **Database** | PostgreSQL 17 (Docker local / Neon cloud) |
| **Scheduling** | GitHub Actions cron (prod), APScheduler (local) |
| **Containerization** | Docker, Docker Compose |
| **Package Manager** | `uv` (Python), `npm` (Node.js) |

---

## Project Structure

```
ai-news/
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml              # Python dependencies (uv)
│   ├── get_gmail_token.py          # OAuth2 token generation helper
│   └── app/
│       ├── main.py                 # Worker daemon + pipeline orchestration
│       ├── api.py                  # FastAPI endpoints (subscribe, cron trigger, unsubscribe)
│       ├── config.py               # Environment variable loader
│       ├── database.py             # SQLAlchemy engine + session factory
│       ├── models.py               # ORM models (User, Source, Content, DigestLog)
│       ├── processor.py            # Gemini LLM summarization with Pydantic validation
│       ├── curator.py              # Preference-based scoring + dedup engine
│       ├── email_service.py        # Gmail API delivery + Jinja2 rendering
│       ├── scraper/
│       │   ├── orchestrator.py     # Source seeding + scraper dispatch
│       │   └── rss_scraper.py      # Universal RSS feed parser
│       └── templates/
│           ├── digest.html         # Daily digest email template
│           └── welcome.html        # Welcome email template
├── frontend/
│   ├── Dockerfile
│   └── src/app/
│       ├── page.tsx                # Landing page with subscription form
│       ├── layout.tsx              # Root layout
│       ├── globals.css             # Design system (dark mode, glassmorphism)
│       └── unsubscribe/
│           └── page.tsx            # Unsubscribe confirmation page
├── .github/
│   └── workflows/
│       └── daily_pipeline.yml      # Scheduled cron to trigger pipeline daily
├── docker-compose.yml              # Local multi-service orchestration
├── .env                            # Environment variables (not committed)
└── README.md
```

---

## Getting Started

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- A [Google Gemini API Key](https://aistudio.google.com/apikey)
- *(Optional)* Gmail OAuth2 credentials for email delivery

### 1. Clone the Repository

```bash
git clone https://github.com/BhuvanDamodar/briefly.ai-Newsletter.git
cd briefly.ai-Newsletter
```

### 2. Configure Environment Variables

Create a `.env` file in the project root:

```env
# ── Database ──
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=ainews
DATABASE_URL=postgresql://postgres:your_secure_password@db:5432/ainews

# ── LLM ──
LLM_API_KEY=your_gemini_api_key
LLM_MODEL=gemini-2.5-flash

# ── Email (Optional - omit for mock console output) ──
FROM_EMAIL=your_email@gmail.com
GMAIL_TOKEN_B64=your_base64_encoded_oauth_token

# ── URLs ──
FRONTEND_URL=http://localhost:3000
API_URL=http://localhost:8000
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 3. Start All Services

```bash
docker-compose up --build
```

This spins up four containers:

| Container | Port | Purpose |
|-----------|------|---------|
| `db` | `5432` | PostgreSQL database |
| `api` | `8000` | FastAPI REST API |
| `worker` | - | Runs the scrape → process → deliver pipeline |
| `frontend` | `3000` | Next.js landing page |

### 4. Visit the App

- **Landing Page:** [http://localhost:3000](http://localhost:3000)
- **API Health Check:** [http://localhost:8000](http://localhost:8000)
- **API Docs (Swagger):** [http://localhost:8000/docs](http://localhost:8000/docs)

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Health check |
| `GET` | `/api/cron/trigger` | Triggers the full pipeline as a background task |
| `POST` | `/api/subscribe` | Subscribe a new user `{ "email": "...", "preferences": [...] }` |
| `GET` | `/api/preferences/{email}` | Retrieve a user's current preferences |
| `GET` | `/api/unsubscribe?email=...` | Deactivate a user's subscription |

---

## Deployment

The production architecture is designed to be **100% free** with no credit card required.

| Component | Provider | Tier |
|-----------|----------|------|
| Backend API | [Render](https://render.com) | Free Web Service |
| Database | [Neon](https://neon.tech) | Free Tier PostgreSQL |
| Frontend | [Vercel](https://vercel.com) | Free Hobby Plan |
| Scheduler | [GitHub Actions](https://github.com/features/actions) | Free (2,000 min/month) |
| Email | Gmail REST API | Free (500 emails/day) |
| AI/LLM | Google Gemini | Free Tier |

### Deployment Steps

1. **Database** - Create a free Neon project and copy the connection string.
2. **Backend** - Create a Render Web Service pointing to the `backend/` directory. Set environment variables (`DATABASE_URL`, `LLM_API_KEY`, `GMAIL_TOKEN_B64`, etc.) in the Render dashboard.
3. **Frontend** - Import the repository to Vercel. Set `NEXT_PUBLIC_API_URL` to your Render service URL.
4. **Scheduler** - The included GitHub Actions workflow (`.github/workflows/daily_pipeline.yml`) automatically triggers the pipeline at 5:00 AM UTC (7:00 AM CET) daily. It first wakes the Render free-tier server from cold sleep, waits for boot, then triggers the pipeline endpoint.

---

## Gmail OAuth2 Setup

To enable real email delivery (instead of mock console output):

1. Create a Google Cloud project and enable the **Gmail API**.
2. Create OAuth2 credentials (Desktop App type).
3. Run the token helper script:
   ```bash
   cd backend
   python get_gmail_token.py
   ```
4. The script outputs a base64 string. Set it as the `GMAIL_TOKEN_B64` environment variable.

---

