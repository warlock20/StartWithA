# Investment Research Platform

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

A platform that connects research, portfolio monitoring, and journaling into one disciplined investment workflow. The goal: help the investor follow a consistent process, learn from every decision, and stay focused — away from the daily noise.

## Core Flow

```
Idea → Kill Screen → Research → Buy Decision → Track Position → Journal → Learn → Better Research
```

**Research** — Idea inbox, kill screening, company & sector research, AI assistant
**Portfolio** — Position tracking, thesis vs reality, checkpoints, AI analytics
**Journal** — Decision journal, mistake log, learning insights

## Tech Stack

- **Backend:** Python 3.12, Flask, PostgreSQL (pgvector), Celery + Redis
- **Frontend:** Jinja2 + React components, Bootstrap, Webpack
- **AI:** Gemini, OpenAI, and Anthropic (via YAML prompt templates)

---

## Quick Start (Docker)

Requires [Docker](https://docs.docker.com/get-docker/) and Docker Compose.

```bash
git clone https://github.com/warlock20/investment-checklist.git
cd investment-checklist
cp .env.example .env    # edit with your Auth0 + API keys (see below)
docker compose up --build -d
```

The app will be available at **http://localhost:8000**.

### Services

| Service    | Description                      | Port   |
|------------|----------------------------------|--------|
| **web**    | Flask app via Gunicorn           | `8000` |
| **db**     | PostgreSQL 16 + pgvector         | `5432` |
| **redis**  | Redis 7 (Celery broker + cache)  | `6379` |
| **worker** | Celery background worker         | —      |

Database migrations run automatically on first startup.

### Useful Commands

```bash
docker compose logs -f web          # follow web logs
docker compose logs -f worker       # follow worker logs
docker compose restart web          # restart after .env changes
docker compose down                 # stop everything
docker compose down -v              # stop and wipe database
```

### Admin Access

1. Register an account through the UI
2. Add your email to `ADMIN_EMAILS` in `.env`
3. Restart: `docker compose restart web`
4. Navigate to `/admin`

---

## Development Setup (without Docker)

Requires Python 3.12+, PostgreSQL with the [pgvector](https://github.com/pgvector/pgvector) extension, Redis, and Node.js.

```bash
git clone https://github.com/warlock20/investment-checklist.git
cd investment-checklist

# Python
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Frontend
npm ci && npm run build

# Environment
cp .env.example .env
# Edit .env — set DATABASE_URL, REDIS_URL, Auth0 keys, etc.

# Database
flask db upgrade

# Run
flask run
```

Start the Celery worker in a separate terminal:

```bash
celery -A celery_app worker --loglevel=info
```

---

## Environment Variables

Copy `.env.example` to `.env`. Docker Compose sets `DATABASE_URL` and `REDIS_URL` automatically — only set those if running without Docker.

### Required

| Variable | Description |
|---|---|
| `SECRET_KEY` | Flask session secret — any random string |
| `AUTH0_DOMAIN` | Your Auth0 tenant domain (e.g. `your-tenant.auth0.com`) |
| `AUTH0_CLIENT_ID` | Auth0 application client ID |
| `AUTH0_CLIENT_SECRET` | Auth0 application client secret |
| `AUTH0_CALLBACK_URL` | OAuth callback URL (`http://localhost:8000/auth/callback` for Docker) |
| `AUTH0_AUDIENCE` | Auth0 API audience (usually `https://<domain>/userinfo`) |
| `GEMINI_API_KEY` | Google Gemini API key — at least one AI provider is needed |

### Optional

| Variable | Description | Default |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI API key (alternative AI provider) | — |
| `ANTHROPIC_API_KEY` | Anthropic API key (alternative AI provider) | — |
| `NEWS_API_KEY` | [NewsAPI](https://newsapi.org/) key for market news | — |
| `ADMIN_EMAILS` | Comma-separated emails that get admin access | — |
| `DATABASE_URL` | PostgreSQL connection string | set by Docker Compose |
| `REDIS_URL` | Redis connection string | set by Docker Compose |
| `DEFAULT_USER_TIER` | Default tier for new users (`free` or `premium`) | `free` |
| `FLASK_DEBUG` | Enable debug mode | `False` |
| `SESSION_COOKIE_SECURE` | Require HTTPS for cookies | `True` |
| `UPLOAD_FOLDER` | Path for file uploads | `instance/uploads` |

### Auth0 Setup

1. Create a free account at [auth0.com](https://auth0.com)
2. Create a **Regular Web Application**
3. In Settings, set **Allowed Callback URLs** to:
   - `http://localhost:8000/auth/callback` (Docker)
   - `http://localhost:5000/auth/callback` (local `flask run`)
4. Copy **Domain**, **Client ID**, and **Client Secret** into your `.env`

---

## Hosted Version

Don't want to self-host? A managed, hosted instance is available — [open a discussion](https://github.com/warlock20/investment-checklist/discussions) to request access.

---

## Contributing

1. Fork the repo and create a feature branch from `develop`
2. Make your changes
3. Run the app locally to verify your changes work
4. Open a pull request against `develop`

Please keep PRs focused — one feature or fix per PR.

---

## License

This project is licensed under the [GNU Affero General Public License v3.0](LICENSE).

This means you can use, modify, and distribute this software, but if you run a modified version on a server, you must make your source code available to users of that server. See the [full license text](LICENSE) for details.
