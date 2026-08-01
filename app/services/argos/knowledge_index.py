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

Indexes the four knowledge sources (research findings, journal entries, decision
journals, saved resources) into ``KnowledgeChunk`` rows: each item is summarised
to a short factual string, embedded once (BGE-base, 768 dims), and upserted keyed
by ``(source_type, source_id)`` so re-running is idempotent.

Long items are summarised via a tunable YAML prompt (``companion/knowledge_summary``);
short items pass through unchanged to avoid a needless LLM call.
"""

import logging

from app import db
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.research import ResearchProject
from app.models.journal import JournalEntry, DecisionJournal
from app.models.company import Company, CompanyResource
from app.models.idea_pipeline import MistakeLog
from app.services.ai import ai_service
from app.services.ai.embedding_service import get_embedding_service
from app.services.ai.prompt_service import prompt_service, resolve_model_provider
from app.utils.blocknote_utils import blocknote_to_text
from app.utils.db_utils import safe_commit

logger = logging.getLogger(__name__)

_MAX_WORDS = 60


def _summarise(user_id, source_type, raw):
    """Short text passes through; long text is summarised via YAML prompt.

    Journal content is stored as BlockNote JSON, so it is flattened to plain text
    first. Indexing it raw embeds the editor's own markup — block ids, `props`,
    `textColor` — which both dilutes the vector and surfaces JSON to the reader.
    The helper passes plain text and old Quill HTML through unchanged.
    """
    raw = blocknote_to_text(raw or '').strip()
    if not raw:
        return ''
    if len(raw.split()) <= _MAX_WORDS:
        return raw
    try:
        prompt_data = prompt_service.get_prompt_with_metadata(
            'companion', 'knowledge_summary',
            source_type=source_type, max_words=_MAX_WORDS, content=raw[:4000])
        model_enum, provider_enum = resolve_model_provider(
            prompt_data.get('metadata', {}), user_id=user_id, prompt_category='companion')
        summary = ai_service.generate_text(
            prompt_data['prompt'], model=model_enum, provider=provider_enum,
            max_tokens=120, temperature=0.2)
        return (summary or '').strip() or raw[:400]
    except Exception as e:
        logger.warning(f"knowledge summary failed ({source_type}): {e}")
        return raw[:400]


def _mistake_text(mistake):
    """Flatten a MistakeLog into one embeddable string (what + lesson)."""
    parts = [mistake.title or '', mistake.description or '']
    if mistake.lesson_learned:
        parts.append(f"Lesson: {mistake.lesson_learned}")
    return '. '.join(p for p in parts if p)


def _upsert(user_id, company_id, source_type, source_id, title, raw):
    """Create or update one KnowledgeChunk. Returns the row, or None if empty."""
    summary = _summarise(user_id, source_type, raw)
    if not summary:
        return None

    embedding = get_embedding_service().embed(summary)

    # Always scope the lookup by user_id (defence-in-depth; source ids are
    # globally-unique PKs so cross-user collision can't happen, but we never
    # query without user_id).
    row = KnowledgeChunk.query.filter_by(
        user_id=user_id, source_type=source_type, source_id=source_id).first()
    if row is None:
        row = KnowledgeChunk(source_type=source_type, source_id=source_id)
        db.session.add(row)

    row.user_id = user_id
    row.company_id = company_id
    row.title = (title or '')[:300]
    row.summary = summary
    row.embedding = embedding.tolist() if embedding is not None else None
    row.token_estimate = max(1, len(summary) // 4)
    return row


def index_company_knowledge(user_id, company_id):
    """(Re)index all knowledge for one company. Returns the number of chunks."""
    count = 0

    # Research findings (one chunk per finding; stable id from project + position)
    projects = ResearchProject.query.filter_by(
        user_id=user_id, company_id=company_id).all()
    for proj in projects:
        for i, finding in enumerate(proj.key_findings or []):
            if _upsert(user_id, company_id, 'finding',
                       proj.id * 1000 + i, 'Finding', str(finding)):
                count += 1

    # Journal entries (free-form notes)
    for entry in JournalEntry.query.filter_by(
            user_id=user_id, company_id=company_id).all():
        if _upsert(user_id, company_id, 'journal', entry.id, entry.title, entry.content):
            count += 1

    # Decision journals (structured theses)
    for decision in DecisionJournal.query.filter_by(
            user_id=user_id, company_id=company_id).all():
        if _upsert(user_id, company_id, 'decision', decision.id,
                   'Decision', decision.investment_thesis):
            count += 1

    # Saved resources (links + files: index title/description)
    for resource in CompanyResource.query.filter_by(
            user_id=user_id, company_id=company_id).all():
        raw = resource.description or resource.title
        if _upsert(user_id, company_id, 'resource', resource.id, resource.title, raw):
            count += 1

    # Logged mistakes tied to this company (blind-spot detector signal)
    for mistake in MistakeLog.query.filter_by(
            user_id=user_id, company_id=company_id).all():
        if _upsert(user_id, company_id, 'mistake', mistake.id,
                   mistake.title, _mistake_text(mistake)):
            count += 1

    safe_commit(db.session, 'index company knowledge')
    return count


def index_general_knowledge(user_id):
    """(Re)index the user's knowledge that isn't tied to any company.

    General notes and general mistakes carry ``company_id IS NULL`` and would be
    missed by the per-company pass, so they get their own path.
    """
    count = 0

    for entry in JournalEntry.query.filter_by(
            user_id=user_id, company_id=None).all():
        if _upsert(user_id, None, 'journal', entry.id, entry.title, entry.content):
            count += 1

    for mistake in MistakeLog.query.filter_by(
            user_id=user_id, company_id=None).all():
        if _upsert(user_id, None, 'mistake', mistake.id,
                   mistake.title, _mistake_text(mistake)):
            count += 1

    safe_commit(db.session, 'index general knowledge')
    return count


def index_user_knowledge(user_id):
    """(Re)index all of a user's knowledge — every company plus general items."""
    total = 0
    for company in Company.query.filter_by(user_id=user_id).all():
        total += index_company_knowledge(user_id, company.id)
    total += index_general_knowledge(user_id)
    return total
