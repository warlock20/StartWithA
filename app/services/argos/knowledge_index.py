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
Knowledge index builder for the companion.

Indexes a user's journal entries (findings included), decision journals, logged
mistakes and saved resources into ``KnowledgeChunk`` rows, one per piece:

    raw text ──► split ──► contextualize ──► embed ──► store

A run only looks at what needs it, so a night with no changes costs a few
indexed queries and no LLM or embedding call:

- items changed since ``User.knowledge_indexed_at`` (the start of the last
  finished run), plus items whose chunks are stale: their context method is not
  what the user should get now (opt-out, budget back) or their embedding model
  is not the current one;
- of those, items whose content hash, context method and embedding model all
  still match are skipped;
- chunks whose item was deleted are removed with one anti-join per source.

Indexing sends note text to the AI provider, so it requires the user's general
AI consent. Without it the user's chunks are deleted and nothing is sent.
"""

import logging
from dataclasses import dataclass

from sqlalchemy import delete, exists, func, or_

from app import db
from app.models import BackgroundTask, CompanyResource, User
from app.models.company import Company
from app.models.idea_pipeline import MistakeLog
from app.models.journal import DecisionJournal, JournalEntry
from app.models.knowledge_chunk import KnowledgeChunk
from app.services.ai.embedding_service import get_embedding_service
from app.services.argos.knowledge_chunking import split
from app.services.argos.knowledge_context import LLM, LLMContextualizer, SourceDoc, contextualize, wanted_method
from app.services.findings import DEFAULT_SIGNAL, FINDING_LABELS
from app.utils.blocknote_utils import blocknote_to_text
from app.utils.time_utils import ensure_timezone_aware, now_utc

logger = logging.getLogger(__name__)

# BackgroundTask.task_type of scheduled and manual index runs.
TASK_TYPE = 'knowledge_index'

# Items processed per run. A first run over a large account stops here and leaves
# the watermark alone; the next run's hash check skips what is already done.
MAX_ITEMS_PER_RUN = 100

# KnowledgeChunk.embedding is Vector(768). A fallback provider with another size
# (TF-IDF is 512) can't be stored.
EMBEDDING_DIMENSION = 768

# source_type -> (model, the column that moves when its indexed text changes).
# Resources are create/delete only, so created_at is enough.
_SOURCES = {
    'journal': (JournalEntry, func.coalesce(JournalEntry.updated_at, JournalEntry.created_at)),
    'decision': (DecisionJournal, func.coalesce(DecisionJournal.updated_at, DecisionJournal.created_at)),
    'mistake': (MistakeLog, func.coalesce(MistakeLog.updated_at, MistakeLog.created_at)),
    'resource': (CompanyResource, CompanyResource.created_at),
}
SOURCE_TYPES = tuple(_SOURCES)


class IndexUnavailable(Exception):
    """The index can't be built right now. The message may be shown to the user."""


@dataclass
class IndexRun:
    consent: bool = True
    items_indexed: int = 0
    chunks_written: int = 0
    chunks_removed: int = 0
    remaining: int = 0


def index_user_knowledge(user_id, on_work=None):
    """Bring one user's knowledge index up to date. Returns an IndexRun.

    on_work(n) is called once, before any LLM or embedding call, when n items
    need indexing; it isn't called on a run with nothing to do.
    """
    user = db.session.get(User, user_id)
    started = now_utc().replace(tzinfo=None)
    run = IndexRun()

    if not user.ai_consent_given:
        run.consent = False
        run.chunks_removed = _execute_delete(delete(KnowledgeChunk).where(KnowledgeChunk.user_id == user_id))
        user.knowledge_indexed_at = started
        db.session.commit()
        return run

    embedder = get_embedding_service()
    model = embedder.model_id
    if model is None or embedder.dimension != EMBEDDING_DIMENSION:
        raise IndexUnavailable('No embedding provider is available. Try again later.')

    run.chunks_removed = _remove_orphans(user_id)
    db.session.commit()

    wanted = wanted_method(user)
    docs = _pending_docs(user, wanted, model)
    if docs and on_work:
        on_work(len(docs))

    batch = docs[:MAX_ITEMS_PER_RUN]
    run.remaining = len(docs) - len(batch)
    llm = LLMContextualizer(user_id) if wanted == LLM else None
    for doc in batch:
        run.chunks_written += _replace_chunks(user_id, doc, llm, embedder, model)
        run.items_indexed += 1
        db.session.commit()

    if llm and llm.tokens_used:
        user.increment_ai_tokens(llm.tokens_used)
    if run.remaining == 0:
        user.knowledge_indexed_at = started
    db.session.commit()
    logger.info(f"knowledge index for user {user_id}: {run}")
    return run


def index_status(user):
    """The user's own index, for the settings page: consent, last check, piece counts, last run."""
    counts = dict(db.session.query(KnowledgeChunk.context_method, func.count(KnowledgeChunk.id))
                  .filter(KnowledgeChunk.user_id == user.id)
                  .group_by(KnowledgeChunk.context_method))
    last_run = (BackgroundTask.query.filter_by(user_id=user.id, task_type=TASK_TYPE)
                .order_by(BackgroundTask.created_at.desc()).first())
    return {
        'consent': bool(user.ai_consent_given),
        'context_enabled': user.knowledge_context_enabled,
        'last_checked': _iso(user.knowledge_indexed_at),
        'pieces': sum(counts.values()),
        'llm_pieces': counts.get(LLM, 0),
        'prefix_pieces': sum(n for method, n in counts.items() if method != LLM),
        'last_run': {
            'id': last_run.id,
            'status': last_run.status,
            'started_at': _iso(last_run.started_at),
            'completed_at': _iso(last_run.completed_at),
            'error': last_run.error_message,
        } if last_run else None,
    }


def _iso(value):
    return ensure_timezone_aware(value).isoformat() if value else None


def _remove_orphans(user_id):
    """Delete the user's chunks whose item no longer exists, or whose source type is retired."""
    removed = _execute_delete(delete(KnowledgeChunk).where(
        KnowledgeChunk.user_id == user_id, KnowledgeChunk.source_type.notin_(SOURCE_TYPES)))
    for source_type, (model, _) in _SOURCES.items():
        source_exists = exists().where(model.id == KnowledgeChunk.source_id, model.user_id == KnowledgeChunk.user_id)
        removed += _execute_delete(delete(KnowledgeChunk).where(
            KnowledgeChunk.user_id == user_id, KnowledgeChunk.source_type == source_type, ~source_exists))
    return removed


def _execute_delete(statement):
    return db.session.execute(statement.execution_options(synchronize_session=False)).rowcount


def _pending_docs(user, wanted, model):
    """Items that changed since the last run or have stale chunks, minus those still up to date."""
    keys = set()
    for source_type, (source_model, changed) in _SOURCES.items():
        query = db.session.query(source_model.id).filter(source_model.user_id == user.id)
        if user.knowledge_indexed_at is not None:
            query = query.filter(changed > user.knowledge_indexed_at)
        keys.update((source_type, row_id) for (row_id,) in query)

    stale = db.session.query(KnowledgeChunk.source_type, KnowledgeChunk.source_id).filter(
        KnowledgeChunk.user_id == user.id,
        or_(KnowledgeChunk.context_method.is_distinct_from(wanted),
            KnowledgeChunk.embedding_model.is_distinct_from(model)),
    ).distinct()
    keys.update((source_type, source_id) for source_type, source_id in stale if source_type in _SOURCES)

    return [doc for doc in _load_docs(user.id, keys) if not _up_to_date(user.id, doc, wanted, model)]


def _up_to_date(user_id, doc, wanted, model):
    chunks = db.session.query(
        KnowledgeChunk.content_hash, KnowledgeChunk.context_method, KnowledgeChunk.embedding_model,
    ).filter_by(user_id=user_id, source_type=doc.source_type, source_id=doc.source_id).all()
    if not chunks:
        return not doc.text
    return all(chunk == (doc.content_hash, wanted, model) for chunk in chunks)


def _load_docs(user_id, keys):
    ids_by_type = {}
    for source_type, source_id in keys:
        ids_by_type.setdefault(source_type, []).append(source_id)

    rows = []
    for source_type, ids in ids_by_type.items():
        source_model = _SOURCES[source_type][0]
        rows += [(source_type, row) for row in source_model.query.filter(
            source_model.user_id == user_id, source_model.id.in_(ids))]

    company_ids = {row.company_id for _, row in rows if row.company_id}
    names = dict(db.session.query(Company.id, Company.name).filter(Company.id.in_(company_ids))) if company_ids else {}
    return [_doc(source_type, row, names.get(row.company_id)) for source_type, row in rows]


def _doc(source_type, row, company_name):
    if source_type == 'journal':
        title, text = _journal_title(row), _text(row.content)
    elif source_type == 'decision':
        title, text = f'{(row.decision_type or "").capitalize()} decision'.strip(), _text(row.investment_thesis)
    elif source_type == 'mistake':
        title, text = row.title or '', _mistake_text(row)
    else:
        title, text = row.title or '', (row.description or row.title or '').strip()
    return SourceDoc(source_type=source_type, source_id=row.id, company_id=row.company_id,
                     company_name=company_name, title=title, text=text)


def _text(content):
    """Plain text, one editor block per line, so the splitter sees paragraphs."""
    return blocknote_to_text(content or '', block_separator='\n').strip()


def _journal_title(entry):
    """Findings are titled with their signal only, so prepend what kind of finding it is."""
    label = FINDING_LABELS.get(entry.entry_type)
    if label is None:
        return entry.title or ''
    if not entry.title or entry.title == DEFAULT_SIGNAL:
        return label
    return f'{label}: {entry.title}'


def _mistake_text(mistake):
    """A MistakeLog as text: what happened, then the lesson."""
    parts = [mistake.title or '', _text(mistake.description)]
    if mistake.lesson_learned:
        parts.append(f"Lesson: {mistake.lesson_learned}")
    return '\n'.join(p for p in parts if p)


def _replace_chunks(user_id, doc, llm, embedder, model):
    """Replace all of an item's pieces. Returns how many were written.

    Delete first: the hash is per item but rows are per piece, so an item that
    got shorter would otherwise leave its old trailing pieces behind.
    """
    _execute_delete(delete(KnowledgeChunk).where(
        KnowledgeChunk.user_id == user_id,
        KnowledgeChunk.source_type == doc.source_type,
        KnowledgeChunk.source_id == doc.source_id))

    pieces = split(doc.text)
    if not pieces:
        return 0
    contexts, method = contextualize(doc, pieces, llm)

    for index, (piece, context) in enumerate(zip(pieces, contexts)):
        vector = embedder.embed(f'{context}\n\n{piece}')
        db.session.add(KnowledgeChunk(
            user_id=user_id, company_id=doc.company_id,
            source_type=doc.source_type, source_id=doc.source_id, chunk_index=index,
            title=doc.title[:300], summary=piece, context=context, context_method=method,
            content_hash=doc.content_hash,
            embedding=vector.tolist() if vector is not None else None,
            # NULL marks a failed embedding, so the next run's stale check retries it.
            embedding_model=model if vector is not None else None,
            token_estimate=max(1, len(piece) // 4),
        ))
    return len(pieces)
