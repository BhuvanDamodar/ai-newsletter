# AI News System Architecture & Pipeline Plan

This document outlines the architecture, pipeline flow, and implementation plan for the Intelligent AI News System. Your goal is to scrape AI-related content, process it using LLMs, curate it based on user preferences, and deliver personalized daily email digests to them.

## 1. System Architecture

The system will use a modular architecture, easily packaged and deployed via Docker Compose.

*   **Database**: PostgreSQL for storing sources, raw content, parsed content, user profiles, generated summaries, and delivery logs.
*   **Orchestrator/Scheduler**: A scheduler (e.g., Celery + Redis, or a simple Python `APScheduler` for a more minimal setup) to trigger periodic scraping and email pipelines.
*   **Scraping Module**: Modular scrapers for different platforms like YouTube and RSS feeds.
*   **Processing Module**: Cleans up raw data formats (e.g., convert HTML/XML to Markdown) and interacts with the LLM API to summarize content.
*   **Curation Module**: Matches processed content with specific user profiles utilizing an LLM prompt that scores relevance.
*   **Delivery Module**: Constructs the final daily email using templates and sends it via an SMTP service (e.g., SendGrid, Mailgun, or standard SMTP).
*   **LLM Integration**: A unified interface (using `Langchain` or `LiteLLM`) to communicate with OpenAI, Anthropic, or local open-weights models.

## 2. Pipeline Flow

The core workflow will be executed sequentially on a daily schedule:

**Stage 1: Scraping**
*   Read configured sources (YouTube channel IDs, RSS feed URLs) from the database or config.
*   Run the RSS Scraper to fetch new articles within the last 24 hours.
*   Run the YouTube Scraper to fetch new videos and extract their transcripts.
*   Save the raw content (HTML, transcripts, metadata) into the `content` table in Postgres with status = `PENDING_PROCESSING`.

**Stage 2: Processing**
*   Fetch all `PENDING_PROCESSING` content from the database.
*   Convert content formats into clean Markdown.
*   Call the LLM to generate concise, standardized summaries for each piece of content.
*   Save the summaries back to the database and update status to `PROCESSED`.

**Stage 3: Curation & Personalization**
*   Fetch all active user profiles and their topic preferences/keywords (e.g., "Agentic AI", "Computer Vision").
*   For each user, fetch the `PROCESSED` content from the past day.
*   Call the LLM (or use embeddings) to score and rank the content against the user's specific profile/preferences.
*   Select the top *N* most relevant articles/videos for that user.

**Stage 4: Delivery**
*   Generate the Daily Digest email using an HTML template engine (like Jinja2) containing the personalized summaries and original links.
*   Send the email using an active SMTP relay.
*   Log the delivery success in the database so the user isn't spammed with duplicates.

## 3. Technology Stack Recommendation

*   **Language**: Python 3.11+
*   **Database**: PostgreSQL
*   **Scraping**: `feedparser` (for RSS), `yt-dlp` or official API (for YouTube), `youtube-transcript-api` (for getting captions).
*   **LLM Integration**: `langchain` or `litellm`
*   **Deployment**: Docker & Docker Compose
*   **Email**: `smtplib` + `Jinja2` templates

## 4. Database Schema Idea (High-Level)

*   `users`: Tracks user preferences (JSON list of interests) and email.
*   `sources`: Registers YouTube channels and RSS links to scrape.
*   `content`: The hub for scraped items storing title, url, raw format, markdown format, and processing state.
*   `curated_digests`: Records what content was sent to which user and when.

## User Review Required

> [!IMPORTANT]
> Please review the proposed architecture and pipeline flow.
> Let me know if you would like me to proceed with setting up the project structure and Docker Compose file, or if you want to adjust the technology stack or pipeline behavior first!
