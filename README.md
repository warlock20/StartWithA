# Investment Research Platform

A platform that connects research, portfolio monitoring, and journaling into one disciplined investment workflow.

See [vision.md](vision.md) for the full product vision.

## Three Parts

**Research** — Idea inbox, kill screening, company & sector research, AI assistant
**Portfolio** — Position tracking, thesis vs reality, checkpoints, AI analytics
**Journal** — Decision journal, mistake log, learning insights

## Core Flow

```
Idea → Kill Screen → Research → Buy Decision → Track Position → Journal → Learn → Better Research
```

## Tech Stack

- **Backend:** Flask, PostgreSQL, SQLAlchemy, Celery + Redis
- **AI:** Gemini (via YAML prompt templates)
- **Frontend:** Jinja2, Bootstrap, Chart.js

## Run with Docker (recommended)

The easiest way to run the platform locally. Requires [Docker](https://docs.docker.com/get-docker/) and Docker Compose.

### 1. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

| Variable | Description |
|---|---|
| `SECRET_KEY` | Any random string |
| `FLASK_APP` | `run.py` |
| `ADMIN_EMAILS` | Comma-separated emails to grant admin access |

Optional (for AI features): `GOOGLE_GENAI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`

> `DATABASE_URL` and `REDIS_URL` are set automatically by Docker Compose — any values in `.env` are overridden.

### 2. Start

```bash
docker compose up --build -d
```

The app will be available at **http://localhost:8000**.

### 3. Services

| Service | Description | Port |
|---|---|---|
| **web** | Flask app via Gunicorn | `8000` |
| **db** | PostgreSQL 16 + pgvector | `5432` |
| **redis** | Redis 7 (Celery broker) | `6379` |
| **worker** | Celery background worker | — |

Database migrations run automatically on startup.

### 4. Useful commands

```bash
# View logs
docker compose logs -f web

# Restart after .env changes
docker compose restart web

# Stop everything
docker compose down

# Stop and wipe database
docker compose down -v
```

### 5. Admin access

1. Register an account through the UI
2. Ensure your email is listed in `ADMIN_EMAILS` in `.env`
3. Restart: `docker compose restart web`
4. Navigate to `/admin`

---

## Development Setup (without Docker)

Requires Python 3.12+, PostgreSQL with pgvector, and Redis.

```bash
git clone https://github.com/warlock20/investment-checklist.git
cd investment-checklist
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # set DATABASE_URL, REDIS_URL, etc.
flask db upgrade
flask run
```

Start Celery worker in a separate terminal:

```bash
celery -A celery_app worker --loglevel=info
```

## License

MIT
