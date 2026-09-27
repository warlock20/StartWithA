# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## License Header (AGPL-3.0)

Every new `.py` file MUST start with this license header:

```python
# StartWithA
# Copyright (C) 2024-2026 Kiran Mathews
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
```

This is enforced by CI (`.github/workflows/license-check.yml`, which checks changed `.py` files outside `migrations/`), so PRs fail without it.

## What this is

StartWithA is an investment research, portfolio and journaling platform. The core flow is: idea / Market Sweeper → Kill Screen → Research (company + sector, checklists, AI assist) → Buy decision → Track position (thesis vs reality, checkpoints) → Journal (decisions, mistakes) → Learn, which feeds back into updated checklists. See `vision.md` for the product vision.

Stack: Python 3.12, Flask, SQLAlchemy + Flask-Migrate, PostgreSQL with pgvector, Celery + Redis, Jinja2 templates with React islands built by Webpack, and multi-provider LLMs (Gemini, Claude, DeepSeek).

## Commands

Local development runs natively, not in Docker: `flask run`, a Celery worker, and a local Redis and Postgres. Use the venv at `venv/bin/python`.

```bash
# App
flask db upgrade                                   # apply migrations
flask run                                          # web app
celery -A celery_app worker --loglevel=info        # background worker (needed for AI tasks and imports)
celery -A celery_app beat                          # scheduled jobs (GDPR anonymisation, daily checkpoint analysis)
flask db migrate -m "msg"                          # new migration after model changes

# Python tests (pytest; no config file, run from repo root)
venv/bin/python -m pytest unittests/
venv/bin/python -m pytest unittests/test_companion_agent.py
venv/bin/python -m pytest unittests/test_companion_agent.py::test_name -x

# Frontend
npm run build          # production webpack build → app/static/js/dist/
npm run dev            # webpack watch
npm test               # vitest (jsdom), tests in frontend/src/**/*.test.{js,jsx}
npx vitest run frontend/src/__tests__/market-sweep-focus.test.jsx
```

Tests need Postgres. `unittests/conftest.py` derives a scratch database `<dev_db>_companion_test` from `DATABASE_URL`, creates it on first use, enables pgvector, builds the schema with `create_all`, and deletes all rows after each test. SQLite cannot render the schema because of the pgvector columns. Embeddings are stubbed in tests.

There is no lint or format tooling configured.

Deployment is on Railway with the Dockerfile. `railway.toml` is the web service (gunicorn `run:app`, `/health` healthcheck) and `railway.worker.toml` is the Celery worker. `docker-entrypoint.sh` runs `flask db upgrade` for the web service only.

## Architecture

### App factory and blueprints
`app/__init__.py:create_app` wires up SQLAlchemy, Migrate, Login, Cache, Limiter, Flask-Admin and Flask-Assets, then registers one blueprint per feature area: `auth`, `checklists`, `companies`, `main`, `dashboard`, `learning`, `question_bank`, `sectors`, `ideas`, `research_workflow`, `analytics`, `journal_enhanced`, `api`, `portfolio`, `settings`, and `companion`. Each blueprint package owns its `routes.py` and `templates/`. On startup the app seeds market sweeps. With `DEMO_MODE=true` it also bootstraps the schema and a demo user (`demo@startwithai.local` / `demo`).

- `app/models/`: all SQLAlchemy models, re-exported from `app/models/__init__.py`. Model modules do `from app import db`.
- `app/services/`: business logic. Routes should stay thin and call into services.
- `app/features.py`: feature gating. `FEATURE_TIERS` maps a feature to `core` or `pro`, and `TIER_ACCESS` maps a user's `subscription_tier` to the tiers it can see. Use `user_has_feature` and the decorators in `app/utils/decorators.py`.
- `config.py`: everything comes from env vars. Without `REDIS_URL` the cache and rate limiter fall back to in-memory.

### AI layer (`app/services/ai/`)
- `ai_service.py` is the single entry point for LLM calls: `generate_text`, `generate_json`, `generate_with_tools`, and `generate_embeddings`. Provider adapters live in `providers/` (`claude.py`, `gemini.py`, `deepseek.py`, `embeddings/`).
- **Prompts live in YAML** under `prompts/<category>/<name>.yaml` and are loaded by `prompt_service.PromptService` through `get_prompt(category, name, **vars)`. Each YAML file declares `system_context`, `template` (with `{var}` placeholders), and `model` (a `quality`/`fast` alias or a concrete model), plus `max_tokens` and `temperature`. Never write prompts as inline f-strings in Python.
- Model resolution: the prompt's default is used first, then `prompts/ai_routing.yaml` `task_overrides`, then the user's AI preferences (`settings/ai_model_routes.py`, `models/user_ai_preferences.py`). The `AI_QUALITY_MODEL` and `AI_FAST_MODEL` env vars set the aliases (see `ai/config.py`).
- `tool_calling.py` has a provider-agnostic tool loop (`run_tool_loop`), which the companion agent uses.
- `embedding_service.py` handles embeddings stored in pgvector (`models/knowledge_chunk.py`).

### Argos / Companion (`app/services/argos/`)
Argos is the agentic research companion that is mounted globally (the widget is in the base template, and the routes are in `app/companion/`). `ArgosService` in `core.py` is a blind-spot detector over the user's own data: past mistakes, journal entries and research. `CompanionAgent` in `agent.py` runs a tool-calling loop over `tools.py`'s `ToolExecutor`. The tools cover knowledge search (`knowledge_index.py`/`knowledge_search.py` over `KnowledgeChunk`), agenda, checklist and page context. Citations that don't resolve are stripped from answers.

### Background tasks
Long or token-consuming AI work runs in Celery. The pattern:
1. The route creates a `BackgroundTask` row (`models/background_task.py`, via `services/background_tasks.py`) with a composite `task_type` such as `portfolio_analysis:behavioral`, which prevents duplicates per type.
2. The route checks the token budget (`User.can_use_ai_tokens`), enqueues `task.delay(task_id, ...)`, and returns straight away.
3. The Celery task in `app/celery_tasks/tasks_*.py` builds its own app with `create_app()` and updates the row's status and result.
4. The frontend polls a status endpoint.

New task modules must be added to the `include=[...]` list in `celery_app.py`. The full checklist is in `.claude/skills/background_task.md`.

### Frontend
Pages are Jinja templates that extend `main/_base.html`. Interactive parts are React bundles: one webpack entry per feature in `webpack.config.js`, emitted to `app/static/js/dist/<name>.bundle.js` and included by templates. A new entry needs `npm run build` before it shows up. CSS is plain module files in `app/static/css/modules/`, bundled by Flask-Assets (`app/assets.py`) into `css_core` plus one page-group bundle (`css_companies`, `css_portfolio`, `css_learning`). A new CSS module must be added to the right bundle.

Page layout conventions are in `.claude/skills/page-styling.md`. Every page wraps its header in `dashboard-header-card`, uses `dashboard-metrics-strip` and `dashboard-alerts-strip` inside it, uses `priority-lane-grid` for card grids, and uses `position-btn` for action buttons.

## Code rules
- All imports go at the top of the file, never inside functions. This includes tests, `conftest.py` and fixtures. The only exceptions are the existing lazy imports of heavy or optional dependencies (`anthropic`, `sentence_transformers`) and the circular-import guards in `create_app`.
- Never use yfinance for ISINs: it returns a valid but wrong ISIN for some tickers.
