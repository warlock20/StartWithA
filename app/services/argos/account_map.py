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
Account map — the compact, cheap DB skeleton the companion agent sees every turn.

Pure DB queries, no LLM. Gives the model the *shape* of the user's account
(holdings + weights, researched companies + project state, the watchlist) plus the
current page focus, so it knows what exists and what to fetch via tools. Kept small
on purpose (a few hundred tokens once rendered).

The section names match the words the user sees in the app — Portfolio, Watchlist,
Researched — so a question phrased in their vocabulary resolves to real rows
instead of being guessed at.
"""

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app import db
from app.models.portfolio import PortfolioPosition
from app.models.research import ResearchProject
from app.models.journal import JournalEntry, PatternRecognition
from app.models.idea_pipeline import MistakeLog
from app.models.user import User


def _counts_by_company(model, user_id):
    """{company_id -> count} for a user, in one grouped query.

    The None key holds rows not tied to a company (general notes / mistakes).
    """
    rows = (
        db.session.query(model.company_id, func.count(model.id))
        .filter(model.user_id == user_id)
        .group_by(model.company_id)
        .all()
    )
    return {company_id: count for company_id, count in rows}


def build_account_map(user_id, focus=None):
    """Assemble the account skeleton for one user. Returns a plain dict."""
    # Cheap grouped counts of the user's journal + mistake history.
    notes_by_company = _counts_by_company(JournalEntry, user_id)
    mistakes_by_company = _counts_by_company(MistakeLog, user_id)
    patterns_total = PatternRecognition.query.filter_by(user_id=user_id).count()
    journal_general = notes_by_company.get(None, 0)
    mistakes_general = mistakes_by_company.get(None, 0)
    positions = (
        PortfolioPosition.query
        .options(joinedload(PortfolioPosition.company))
        .filter_by(user_id=user_id, is_active=True)
        .all()
    )
    total_value = sum(float(p.current_value or 0) for p in positions) or 0.0

    holdings = []
    for p in positions:
        company = p.company
        value = float(p.current_value or 0)
        holdings.append({
            'company_id': p.company_id,
            'name': company.name if company else 'Unknown',
            'ticker': company.ticker_symbol if company else None,
            'weight_pct': round(value / total_value * 100, 1) if total_value else 0.0,
            'notes': notes_by_company.get(p.company_id, 0),
            'mistakes': mistakes_by_company.get(p.company_id, 0),
        })
    holdings.sort(key=lambda h: h['weight_pct'], reverse=True)

    researched = (
        ResearchProject.query
        .options(joinedload(ResearchProject.company))
        .filter_by(user_id=user_id)
        .all()
    )
    researched_companies = []
    for proj in researched:
        company = proj.company
        state = proj.status or 'in_progress'
        if proj.current_step_index is not None:
            state = f"{state} (step {proj.current_step_index + 1})"
        researched_companies.append({
            'company_id': proj.company_id,
            'name': company.name if company else 'Unknown',
            'project_state': state,
            'notes': notes_by_company.get(proj.company_id, 0),
            'mistakes': mistakes_by_company.get(proj.company_id, 0),
        })

    # "Watchlist" in the UI is the user's favourited companies — the company page
    # derives its badge the same way, portfolio first (companies/routes.py).
    # Held companies are excluded so a company appears under one heading only.
    held_ids = {h['company_id'] for h in holdings}
    user = db.session.get(User, user_id)
    watchlist = []
    if user is not None:
        for company in user.favorites.all():
            if company.id in held_ids:
                continue
            watchlist.append({
                'company_id': company.id,
                'name': company.name,
                'ticker': company.ticker_symbol,
                'notes': notes_by_company.get(company.id, 0),
                'mistakes': mistakes_by_company.get(company.id, 0),
            })

    company_ids = {h['company_id'] for h in holdings} | {
        r['company_id'] for r in researched_companies} | {
        w['company_id'] for w in watchlist}

    return {
        'holdings': holdings,
        'researched_companies': researched_companies,
        'watchlist': watchlist,
        'focus': focus or {},
        'counts': {
            'holdings': len(holdings),
            'companies': len(company_ids),
            'journal_entries': sum(notes_by_company.values()),
            'journal_general': journal_general,
            'mistakes': sum(mistakes_by_company.values()),
            'mistakes_general': mistakes_general,
            'patterns': patterns_total,
        },
    }


def render_account_map(account_map):
    """Render the account map as a compact text block for the prompt."""
    lines = []
    focus = account_map.get('focus') or {}
    if focus.get('type'):
        target = f" (id={focus['id']})" if focus.get('id') else ''
        lines.append(f"CURRENT FOCUS: {focus['type']}{target}")

    def _tags(item):
        parts = []
        if item.get('notes'):
            parts.append(f"{item['notes']} note(s)")
        if item.get('mistakes'):
            parts.append(f"{item['mistakes']} mistake(s)")
        return f" · {', '.join(parts)}" if parts else ''

    holdings = account_map.get('holdings', [])
    lines.append(f"PORTFOLIO — {len(holdings)} holding(s):")
    if holdings:
        for h in holdings:
            ticker = f" ({h['ticker']})" if h.get('ticker') else ''
            lines.append(f"  - {h['name']}{ticker}: {h['weight_pct']}%{_tags(h)}")
    else:
        lines.append("  - none")

    researched = account_map.get('researched_companies', [])
    if researched:
        lines.append(f"RESEARCHED COMPANIES — {len(researched)}:")
        for r in researched:
            lines.append(f"  - {r['name']}: {r['project_state']}{_tags(r)}")

    # The UI calls these the user's Watchlist; name it the same way so their
    # wording resolves to something instead of being guessed at.
    watchlist = account_map.get('watchlist', [])
    lines.append(
        f"WATCHLIST — {len(watchlist)} company(ies) the user is watching "
        "(favourited, not held):")
    if watchlist:
        for w in watchlist:
            ticker = f" ({w['ticker']})" if w.get('ticker') else ''
            lines.append(f"  - {w['name']}{ticker}{_tags(w)}")
    else:
        lines.append("  - none")

    counts = account_map.get('counts', {})
    history = []
    if counts.get('mistakes'):
        history.append(f"{counts['mistakes']} logged mistake(s)")
    if counts.get('patterns'):
        history.append(f"{counts['patterns']} behavioural pattern(s)")
    if counts.get('journal_general'):
        history.append(f"{counts['journal_general']} general note(s)")
    if history:
        lines.append("HISTORY: " + ", ".join(history))

    return "\n".join(lines)
