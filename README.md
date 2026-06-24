# RCAI — Root Cause AI

Paste an error log, get back a structured root-cause analysis: a summary, ranked root causes with confidence scores and fixes, a five-whys breakdown, affected services, and a recurrence check against your own incident history.

## What changed in this version

- **Auth**: email/password signup & login (Flask-Login, hashed passwords, server + client-side validation, rate-limited).
- **Real AI analysis**: the old fake `RandomForestClassifier` is gone. Analysis now comes from an LLM via the **Hugging Face Inference API** (see "Why Hugging Face API" below).
- **Semantic search removed**: `similarity_service.py`, the `incident_embeddings` table, and `sentence-transformers` are gone. "Have we seen this before?" is now a plain SQL lookup keyed on a `category` tag the model assigns each incident — no embeddings, no extra dependency weight.
- **Redesigned UI**: every page (login, signup, dashboard, new-incident, incidents) rebuilt with a consistent dark "diagnostic trace" visual identity, animated states, and a responsive layout (sidebar collapses to a drawer under 860px).
- **Data model**: incidents now belong to a `user_id`; `root_causes` stores the full structured analysis (summary, root causes, five whys, affected services, category, recurrence count, historical solution).

## Why the Hugging Face Inference API (not Ollama)

The target deployment is a **t3.micro (1 vCPU / 1GB RAM)**. That's not enough headroom to load and run even a small quantized LLM locally alongside Flask — Ollama would either fail to start or starve the rest of the app. Routing inference through Hugging Face's hosted API keeps the EC2 box doing nothing heavier than an HTTPS call; the model (`Qwen/Qwen2.5-7B-Instruct` by default, swappable via `HF_MODEL`) runs on HF's infrastructure.

If you later move to a t3.medium/large, switching to a local Ollama model is a contained change — only `services/ai_service.py` would need a new `_call_ollama_api` path.

## Setup

```bash
cp .env.example .env
# fill in SECRET_KEY, DATABASE_URL (or DB_*), HF_API_TOKEN

pip install -r requirements.txt --break-system-packages   # or use a venv
python scripts/seed_data.py   # optional: creates test@rcai.dev / TestPass123 + sample incidents
python app.py                 # http://localhost:5000
```

Or with Docker (local dev, runs Postgres in a container too):
```bash
docker-compose up --build
```

## Production on a t3.micro

1. **Don't co-host Postgres on the same instance.** Use a managed Postgres — [Neon](https://neon.tech) has a free tier that works well here. Set `DATABASE_URL` in `.env` and only deploy the `app` container (skip the `db` service in `docker-compose.yml`, or run the Dockerfile directly).
2. Get an `HF_API_TOKEN` from [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) (read scope is enough).
3. Set `SESSION_COOKIE_SECURE=true` once you're behind HTTPS (nginx + certbot, or an ALB).
4. The Dockerfile already runs gunicorn with `--workers 1 --threads 4`, sized for 1GB RAM. Don't raise worker count on this instance size.

## Database migration (upgrading an existing v1 deployment)

If you have a live v1 deployment with real incident data, run `scripts/migrate_v1_to_v2.sql` once against your database — it adds the `users` table, attaches existing incidents to a placeholder admin account, extends `root_causes`, and drops the old embeddings table. Fresh installs don't need this; `database/schema.sql` handles everything via `init_db()`.

## User flow

1. Sign up / log in
2. **New Incident** → enter a title, paste the error log, pick a severity
3. AI analyzes it (HF API call, typically a few seconds)
4. Review root causes with confidence scores, the five-whys trace, affected services, and any recurrence history
5. Mark as resolved, or delete if it's a duplicate
6. **Dashboard** shows open/in-progress/resolved/critical counts, a 30-day trend, and root-cause category breakdown

## Stack

Flask · Flask-Login · PostgreSQL (Neon-compatible) · Hugging Face Inference API · vanilla HTML/CSS/JS (no build step) · Chart.js · Gunicorn · Docker
