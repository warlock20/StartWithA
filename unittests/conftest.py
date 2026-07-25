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

"""
Shared pytest fixtures for DB-backed companion tests.

Uses a DEDICATED scratch Postgres database (``<dev_db>_companion_test``) so tests
never touch the dev database. The scratch DB is created on first use, the pgvector
extension is enabled, and the full schema is built with ``create_all``. Each test
runs against it and all rows are deleted afterwards, so tests are isolated without
paying to rebuild the schema every time.

Embeddings are stubbed (``stub_embedding``) to a fixed vector — indexing/retrieval
logic is what we test here, not the embedding model.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import numpy as np
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url

from config import Config
from app import create_app, db
from app.models import User, Company, ResearchProject
from app.models.research import ResearchTemplate
from app.models.journal import JournalEntry
from app.models.idea_pipeline import MistakeLog
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.portfolio import PortfolioPosition

_BASE_URL = make_url(Config.SQLALCHEMY_DATABASE_URI)
_SCRATCH_URL = _BASE_URL.set(database=_BASE_URL.database + '_companion_test')


class TestConfig(Config):
    """Config pointed at the scratch DB; CSRF off for the test client."""
    # render_as_string(hide_password=False) — plain str(url) masks the password as "***".
    SQLALCHEMY_DATABASE_URI = _SCRATCH_URL.render_as_string(hide_password=False)
    TESTING = True
    WTF_CSRF_ENABLED = False


def _ensure_scratch_db():
    """Create the scratch DB (if absent) and enable pgvector.

    Bootstraps from the dev DB connection (known-good credentials) rather than the
    `postgres` maintenance DB, whose auth rules may differ. CREATE DATABASE works
    from any autocommit connection.
    """
    admin = create_engine(_BASE_URL, isolation_level='AUTOCOMMIT')
    try:
        with admin.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :n"),
                {"n": _SCRATCH_URL.database},
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{_SCRATCH_URL.database}"'))
    finally:
        admin.dispose()

    scratch = create_engine(_SCRATCH_URL, isolation_level='AUTOCOMMIT')
    try:
        with scratch.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    finally:
        scratch.dispose()


@pytest.fixture(scope='session')
def _app():
    """Session-scoped Flask app bound to the scratch DB with the schema built."""
    _ensure_scratch_db()
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
    yield app


@pytest.fixture
def app_context(_app):
    """Push an app context; delete all rows afterwards to isolate tests."""
    with _app.app_context():
        yield
        db.session.rollback()
        # Delete children before parents to respect FK constraints.
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()


@pytest.fixture
def stub_embedding(monkeypatch):
    """Replace the embedding service with a deterministic 768-dim vector."""
    class _FakeEmbeddingService:
        def embed(self, text, use_cache=True):
            # Deterministic pseudo-vector seeded by the text, so different texts
            # get different vectors (needed by retrieval-ranking tests).
            rng = np.random.default_rng(abs(hash(text)) % (2 ** 32))
            return rng.random(768, dtype=np.float64)

    fake = _FakeEmbeddingService()
    # Patch every module that resolves the embedding service.
    for modpath in ('app.services.argos.knowledge_index',
                    'app.services.argos.knowledge_search'):
        try:
            monkeypatch.setattr(f'{modpath}.get_embedding_service', lambda: fake)
        except (AttributeError, ImportError):
            pass
    return fake


# =========================================================================
# Seed helpers
# =========================================================================

def _make_user(email='tester@example.com'):
    user = User(email=email)
    db.session.add(user)
    db.session.flush()
    return user


def _make_company(user_id, name='ASML Holding', ticker='ASML'):
    company = Company(name=name, ticker_symbol=ticker, user_id=user_id)
    db.session.add(company)
    db.session.flush()
    return company


def _make_project(user_id, company_id, findings=None):
    template = ResearchTemplate(user_id=user_id, name='T', workflow_steps=[])
    db.session.add(template)
    db.session.flush()
    project = ResearchProject(
        user_id=user_id, company_id=company_id, template_id=template.id,
        key_findings=findings or [],
    )
    db.session.add(project)
    db.session.flush()
    return project


def _make_chunk(user_id, company_id, source_type, source_id, summary):
    chunk = KnowledgeChunk(
        user_id=user_id, company_id=company_id,
        source_type=source_type, source_id=source_id,
        title=source_type, summary=summary,
        embedding=np.random.default_rng(source_id + abs(hash(source_type)) % 1000)
        .random(768).tolist(),
        token_estimate=max(1, len(summary) // 4),
    )
    db.session.add(chunk)
    return chunk


@pytest.fixture
def seed_company_with_findings(app_context):
    """A user + company + a research project carrying two key findings."""
    user = _make_user()
    company = _make_company(user.id)
    _make_project(user.id, company.id, findings=[
        'The company has a durable moat from its distribution network and switching costs.',
        'Management has a consistent capital allocation record over the last decade.',
    ])
    db.session.commit()
    return user.id, company.id


@pytest.fixture
def seed_many_chunks(app_context):
    """One user with 10 chunks in each of finding/journal/resource (30 total)."""
    user = _make_user()
    company = _make_company(user.id)
    for source_type in ('finding', 'journal', 'resource'):
        for i in range(10):
            _make_chunk(user.id, company.id, source_type, i,
                        f'{source_type} {i}: notes on the competitive moat and advantage')
    db.session.commit()
    return user.id


@pytest.fixture
def other_user(app_context):
    """A second user who owns no knowledge."""
    user = _make_user(email='other@example.com')
    db.session.commit()
    return user.id


@pytest.fixture
def seed_two_users(app_context):
    """Two users; the second owns a company. Returns (u1_id, u2_id, u2_company_id)."""
    u1 = _make_user(email='u1@example.com')
    u2 = _make_user(email='u2@example.com')
    db.session.flush()
    u2_company = _make_company(u2.id)
    db.session.commit()
    return u1.id, u2.id, u2_company.id


@pytest.fixture
def seed_portfolio(app_context):
    """A user with two active positions in European companies. Returns user_id."""
    user = _make_user()
    c1 = _make_company(user.id, name='ASML Holding', ticker='ASML')
    c2 = _make_company(user.id, name='SAP SE', ticker='SAP')
    db.session.add(PortfolioPosition(
        user_id=user.id, company_id=c1.id, is_active=True,
        total_shares=100, current_value=140000))
    db.session.add(PortfolioPosition(
        user_id=user.id, company_id=c2.id, is_active=True,
        total_shares=50, current_value=60000))
    db.session.commit()
    return user.id


@pytest.fixture
def seed_portfolio_with_history(app_context):
    """A held company that also has one journal note and one logged mistake.

    Returns (user_id, company_id).
    """
    user = _make_user()
    company = _make_company(user.id)
    db.session.add(PortfolioPosition(
        user_id=user.id, company_id=company.id, is_active=True,
        total_shares=10, current_value=50000))
    db.session.add(JournalEntry(
        user_id=user.id, company_id=company.id, entry_type='observation',
        title='Note', content='An observation about the company.'))
    db.session.add(MistakeLog(
        user_id=user.id, company_id=company.id, title='Overpaid',
        description='Bought above intrinsic value.', mistake_type='valuation',
        lesson_learned='Anchor to a valuation range before buying.'))
    db.session.commit()
    return user.id, company.id


@pytest.fixture
def seed_company_no_project(app_context):
    """A user + company with NO research project and NO position. Returns (uid, cid)."""
    user = _make_user()
    company = _make_company(user.id)
    db.session.commit()
    return user.id, company.id


@pytest.fixture
def seed_company_completed_project(app_context):
    """A user + company with a COMPLETED research project (decision + flags). Returns (uid, cid)."""
    user = _make_user()
    company = _make_company(user.id)
    template = ResearchTemplate(user_id=user.id, name='T', workflow_steps=[])
    db.session.add(template)
    db.session.flush()
    db.session.add(ResearchProject(
        user_id=user.id, company_id=company.id, template_id=template.id,
        status='completed', decision='invest',
        red_flags=['high debt load'], green_flags=['strong cash flow'],
        investment_thesis='Durable moat with pricing power.'))
    db.session.commit()
    return user.id, company.id


@pytest.fixture
def seed_general_knowledge(app_context):
    """A user with a company-less note and a company-less mistake. Returns user_id."""
    user = _make_user()
    db.session.add(JournalEntry(
        user_id=user.id, company_id=None, entry_type='observation',
        title='General note', content='A general reflection not tied to a company.'))
    db.session.add(MistakeLog(
        user_id=user.id, company_id=None, title='Chased momentum',
        description='Bought after a fast run-up without a thesis.',
        mistake_type='behavioural',
        lesson_learned='Require a written thesis before buying.'))
    db.session.commit()
    return user.id


@pytest.fixture
def seed_journal_resource(app_context):
    """A user + company + one real JournalEntry. Returns (user_id, entry_id)."""
    user = _make_user()
    company = _make_company(user.id)
    entry = JournalEntry(
        user_id=user.id, company_id=company.id,
        entry_type='observation', title='Moat note',
        content='A note about the company moat and switching costs.',
    )
    db.session.add(entry)
    db.session.commit()
    return user.id, entry.id
