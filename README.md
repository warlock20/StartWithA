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

## Setup

```bash
git clone https://github.com/warlock20/investment-checklist.git
cd investment-checklist
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # edit as needed
flask --app run.py init-db
flask --app run.py run
```

Start Celery worker (requires Redis):

```bash
celery -A celery_app worker --loglevel=info
```

## License

MIT
