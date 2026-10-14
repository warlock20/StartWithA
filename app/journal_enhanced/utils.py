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

from dataclasses import dataclass
from datetime import datetime, timedelta, date
from app import db
from app.models import (JournalEntry, ThesisEvolution, LearningNote,
                       Company, MistakeLog)
import re
from collections import Counter
from sqlalchemy import String, func, literal, select, text, union_all
from app.utils.time_utils import now_utc

def extract_tags_from_content(content):
    """
    Extract hashtags from journal content.
    """
    pattern = r'#(\w+)'
    tags = re.findall(pattern, content)
    return list(set(tags))  # Remove duplicates

def get_related_entries(entry, limit=5):
    """
    Find related journal entries based on tags, company, and content similarity.
    """
    related = []
    
    # Same company entries
    if entry.company_id:
        company_entries = JournalEntry.query.filter(
            JournalEntry.company_id == entry.company_id,
            JournalEntry.id != entry.id,
            JournalEntry.user_id == entry.user_id
        ).order_by(JournalEntry.created_at.desc()).limit(limit).all()
        related.extend(company_entries)
    
    # Same tags entries - PostgreSQL compatible approach
    if entry.tags:
        # Use text-based search in the JSON field to avoid operator issues
        tag_entries = JournalEntry.query.filter(
            JournalEntry.tags.isnot(None),
            JournalEntry.id != entry.id,
            JournalEntry.user_id == entry.user_id
        ).all()

        # Filter in Python to avoid complex JSON operations
        for tag_entry in tag_entries:
            if tag_entry.tags and any(tag in entry.tags for tag in tag_entry.tags):
                related.append(tag_entry)
                if len(related) >= limit * 2:  # Get more since we're filtering
                    break
    
    # Remove duplicates and limit
    seen = set()
    unique_related = []
    for e in related:
        if e.id not in seen:
            seen.add(e.id)
            unique_related.append(e)
            if len(unique_related) >= limit:
                break
    
    return unique_related

def search_journal(user_id, query, filters=None):
    """
    Enhanced search for journal entries with knowledge hub filters.
    """
    # Base query
    search = JournalEntry.query.filter_by(user_id=user_id, is_archived=False)

    # Text search in content, title, key_insight
    if query:
        search_pattern = f'%{query}%'
        search = search.filter(
            db.or_(
                JournalEntry.content.ilike(search_pattern),
                JournalEntry.title.ilike(search_pattern),
                JournalEntry.key_insight.ilike(search_pattern),
            )
        )

    # Apply filters
    if filters:
        if filters.get('company_id'):
            search = search.filter_by(company_id=filters['company_id'])

        if filters.get('entry_type'):
            search = search.filter_by(entry_type=filters['entry_type'])

        if filters.get('sentiment'):
            search = search.filter_by(sentiment=filters['sentiment'])

        if filters.get('starred_only'):
            search = search.filter_by(is_starred=True)

        if filters.get('reviewed_only'):
            search = search.filter(JournalEntry.last_reviewed.isnot(None))

        # Creation date filters
        if filters.get('date_from'):
            search = search.filter(JournalEntry.created_at >= filters['date_from'])

        if filters.get('date_to'):
            search = search.filter(JournalEntry.created_at <= filters['date_to'])

        # Review date filters (knowledge hub specific)
        if filters.get('review_date_from'):
            search = search.filter(JournalEntry.last_reviewed >= filters['review_date_from'])

        if filters.get('review_date_to'):
            search = search.filter(JournalEntry.last_reviewed <= filters['review_date_to'])

    # Get initial results
    initial_results = search.order_by(JournalEntry.created_at.desc()).all()

    # Apply tag filtering in Python (PostgreSQL compatibility)
    if filters and filters.get('tags'):
        filtered_results = []
        for entry in initial_results:
            if entry.tags and all(tag in entry.tags for tag in filters['tags']):
                filtered_results.append(entry)
        return filtered_results

    return initial_results

def get_all_user_tags(user_id):
    """
    Get all unique tags used by a user, sorted by frequency.
    """
    # Get all entries with tags
    entries_with_tags = JournalEntry.query.filter(
        JournalEntry.user_id == user_id,
        JournalEntry.tags.isnot(None)
    ).all()

    # Collect all tags
    tag_counter = Counter()
    for entry in entries_with_tags:
        if entry.tags:
            tag_counter.update(entry.tags)

    # Return tags sorted by frequency (most common first)
    return [tag for tag, count in tag_counter.most_common()]

def get_journal_statistics(user_id):
    """
    Get statistics about journal usage.
    """
    total_entries = JournalEntry.query.filter_by(user_id=user_id).count()
    
    # Entries by type
    type_counts = db.session.query(
        JournalEntry.entry_type,
        db.func.count(JournalEntry.id)
    ).filter_by(user_id=user_id).group_by(JournalEntry.entry_type).all()
    
    # Most used tags
    all_tags = []
    entries_with_tags = JournalEntry.query.filter_by(user_id=user_id).filter(
        JournalEntry.tags.isnot(None)
    ).all()
    for entry in entries_with_tags:
        if entry.tags:
            all_tags.extend(entry.tags)
    
    tag_counts = Counter(all_tags).most_common(10)
    
    # Recent activity
    last_7_days = now_utc() - timedelta(days=7)
    recent_entries = JournalEntry.query.filter(
        JournalEntry.user_id == user_id,
        JournalEntry.created_at >= last_7_days
    ).count()
    
    # Learning notes stats
    total_lessons = LearningNote.query.filter_by(user_id=user_id).count()

    return {
        'total_entries': total_entries,
        'type_counts': dict(type_counts),
        'top_tags': tag_counts,
        'recent_entries': recent_entries,
        'total_lessons': total_lessons,
    }

# ---------------------------------------------------------------------------
# Knowledge Hub: company-centric reads over research (JournalEntry), wisdom
# (LearningNote) and mistakes (MistakeLog).
# ---------------------------------------------------------------------------

@dataclass
class CompanyNoteCount:
    """Notes per type for one company — one Knowledge Hub dropdown option."""
    id: int
    name: str
    ticker: str
    research: int = 0
    wisdom: int = 0
    mistake: int = 0

    @property
    def total(self):
        return self.research + self.wisdom + self.mistake


def _company_note_rows(user_id):
    """One (company_id, kind, created_at) row per company-linked hub note."""
    research = select(
        JournalEntry.company_id.label('company_id'),
        literal('research', String).label('kind'),
        JournalEntry.created_at.label('created_at'),
    ).where(
        JournalEntry.user_id == user_id,
        JournalEntry.company_id.isnot(None),
        JournalEntry.is_archived.is_(False),
    )
    wisdom = select(
        LearningNote.company_id,
        literal('wisdom', String),
        LearningNote.created_at,
    ).where(
        LearningNote.user_id == user_id,
        LearningNote.company_id.isnot(None),
    )
    mistake = select(
        MistakeLog.company_id,
        literal('mistake', String),
        MistakeLog.created_at,
    ).where(
        MistakeLog.user_id == user_id,
        MistakeLog.company_id.isnot(None),
    )
    return union_all(research, wisdom, mistake).subquery()


def _company_note_counts(user_id, company_id=None):
    """{company_id: CompanyNoteCount}, ordered by company name."""
    notes = _company_note_rows(user_id)
    query = db.session.query(
        Company.id, Company.name, Company.ticker_symbol,
        notes.c.kind, func.count(),
    ).join(
        notes, notes.c.company_id == Company.id
    ).filter(
        # A note pointing at another user's company must not surface it.
        Company.user_id == user_id
    )
    if company_id is not None:
        query = query.filter(Company.id == company_id)
    rows = query.group_by(
        Company.id, Company.name, Company.ticker_symbol, notes.c.kind
    ).order_by(func.lower(Company.name), Company.id).all()

    counts = {}
    for cid, name, ticker, kind, n in rows:
        entry = counts.setdefault(cid, CompanyNoteCount(cid, name, ticker))
        setattr(entry, kind, n)
    return counts


def companies_with_notes(user_id):
    """Companies with at least one research/wisdom/mistake note, A to Z."""
    return list(_company_note_counts(user_id).values())


def get_company_knowledge_summary(user_id, company_id, insight_limit=5, item_limit=10):
    """Everything the Knowledge Hub knows about one company, as a dict.

    Returns None if the company is not the user's. Independent of the hub's
    type/search/tag/starred filters — it describes the company, not the
    current result set.
    """
    company = Company.query.filter_by(id=company_id, user_id=user_id).first()
    if company is None:
        return None

    counts = _company_note_counts(user_id, company_id).get(
        company_id, CompanyNoteCount(company.id, company.name, company.ticker_symbol)
    )

    notes = _company_note_rows(user_id)
    first_note_at, last_note_at = db.session.query(
        func.min(notes.c.created_at), func.max(notes.c.created_at)
    ).filter(notes.c.company_id == company_id).one()

    thesis_versions = ThesisEvolution.query.filter_by(
        user_id=user_id, company_id=company_id
    ).order_by(ThesisEvolution.created_at).all()
    current_thesis = None
    if thesis_versions:
        current = [t for t in thesis_versions if t.is_current]
        current_thesis = current[-1] if current else thesis_versions[-1]

    # Newest first: everything below wants the most recent items.
    entries = JournalEntry.query.filter_by(
        user_id=user_id, company_id=company_id, is_archived=False
    ).order_by(JournalEntry.created_at.desc()).all()

    latest_sentiment = next((e.sentiment for e in entries if e.sentiment), None)
    latest_conviction = next((e.conviction_level for e in entries if e.conviction_level), None)
    key_insights = [e for e in entries if e.key_insight][:insight_limit]
    # These JSON lists carry no resolved/done state, so they are "raised",
    # not "open".
    questions_raised = [(q, e) for e in entries for q in (e.questions_raised or []) if q][:item_limit]
    action_items = [(a, e) for e in entries for a in (e.action_items or []) if a][:item_limit]

    points = [(t.created_at, t.conviction_level)
              for t in thesis_versions if t.created_at and t.conviction_level]
    points += [(e.created_at, e.conviction_level)
               for e in entries if e.created_at and e.conviction_level]
    points.sort(key=lambda p: p[0])

    avg_severity = db.session.query(func.avg(MistakeLog.severity)).filter(
        MistakeLog.user_id == user_id,
        MistakeLog.company_id == company_id,
        MistakeLog.severity.isnot(None),
    ).scalar()

    return {
        'company': company,
        'counts': counts,
        'first_note_at': first_note_at,
        'last_note_at': last_note_at,
        'current_thesis': current_thesis,
        'latest_sentiment': latest_sentiment,
        'latest_conviction': latest_conviction,
        'conviction_points': [(d.date(), c) for d, c in points],
        'conviction_sparkline': conviction_sparkline(points),
        'key_insights': key_insights,
        'questions_raised': questions_raised,
        'action_items': action_items,
        'mistake_avg_severity': round(float(avg_severity), 1) if avg_severity is not None else None,
    }


def conviction_sparkline(points, width=120, height=28, pad=3):
    """SVG polyline coordinates for a conviction series on a fixed 1-10 scale.

    Returns None for fewer than two points — a single dot is not a trend.
    Points are spaced by order, not date, so bursts of notes stay readable.
    """
    if len(points) < 2:
        return None
    step = (width - 2 * pad) / (len(points) - 1)
    span = height - 2 * pad
    coords = []
    for i, (_, conviction) in enumerate(points):
        clamped = min(max(conviction, 1), 10)
        coords.append(f'{pad + i * step:.1f},{pad + span * (10 - clamped) / 9:.1f}')
    return ' '.join(coords)
