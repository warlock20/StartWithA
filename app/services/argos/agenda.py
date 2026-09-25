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
The user's agenda: what is due, stalled, or unanswered — the question shape
semantic search can't serve.

"Which checkpoints are due?" is ``target_date <= today AND status = 'Active'``;
no amount of cosine similarity to the word "due" retrieves that. So this module
answers by filter, not by embedding, across the places work waits on the user:

- destination checkpoints that are overdue or fall within the horizon
- active research projects nobody has touched in a while
- checklist runs still in progress with unanswered questions
- kill-checklist sessions left open with criteria unanswered
- held positions whose actual return is behind their original thesis

Every query is scoped to ``user_id``. Returned items carry the ids a follow-up
tool call needs, plus a ``cite`` tuple ``(source_type, source_id, label)`` the
tool layer turns into a citation number.
"""

from app.models.checklist import DestinationCheckpoint
from app.models.idea_pipeline import KillAnswer, KillSession
from app.models.portfolio import PortfolioPosition
from app.models.research import ChecklistAnalysis, ChecklistAnswer, ResearchProject
from app.services.config_service import ConfigKeys, get_config
from app.services.portfolio_intelligence import PortfolioIntelligenceService
from app.utils.checklist_utils import get_all_ordered_items_for_checklist
from app.utils.time_utils import (
    add_days, days_between, days_until, ensure_timezone_aware, now_utc)

# Fallbacks when a key is missing from SystemConfig. The admin-editable values
# (System Config, category 'companion') are seeded by the add_agenda_config
# migration with these same defaults.
_DEFAULTS = {
    # Days ahead to look for due checkpoints when the model doesn't ask.
    ConfigKeys.AGENDA_DEFAULT_HORIZON_DAYS: 30,
    # Largest horizon the model may request.
    ConfigKeys.AGENDA_MAX_HORIZON_DAYS: 365,
    # An active project untouched for this long counts as stalled.
    ConfigKeys.AGENDA_STALLED_AFTER_DAYS: 45,
    # Per-section cap; totals are reported so the model knows when a list was cut.
    ConfigKeys.AGENDA_MAX_ITEMS: 15,
}
# Thesis-reality statuses that mean "the position is not doing what you expected".
_DRIFT_STATUSES = ('needs_attention', 'behind')


def _as_positive_int(value, fallback):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return fallback
    return number if number >= 1 else fallback


def _settings(user_id):
    """Effective agenda thresholds for this user (system -> profile -> user)."""
    return {key: _as_positive_int(get_config(key, user_id, default), default)
            for key, default in _DEFAULTS.items()}


def _clamp_horizon(horizon_days, settings):
    default = settings[ConfigKeys.AGENDA_DEFAULT_HORIZON_DAYS]
    try:
        horizon = int(horizon_days)
    except (TypeError, ValueError):
        return default
    return max(1, min(horizon, settings[ConfigKeys.AGENDA_MAX_HORIZON_DAYS]))


def _section(items, settings):
    return {'total': len(items),
            'items': items[:settings[ConfigKeys.AGENDA_MAX_ITEMS]]}


def _company_label(company, fallback):
    if not company:
        return fallback
    if company.ticker_symbol:
        return f'{company.name} ({company.ticker_symbol})'
    return company.name


def _checkpoints(user_id, today, horizon):
    """Active checkpoints that are overdue (any age) or due within the horizon."""
    held = {cid for (cid,) in PortfolioPosition.query.with_entities(
        PortfolioPosition.company_id).filter_by(user_id=user_id, is_active=True)}
    rows = (DestinationCheckpoint.query
            .filter(DestinationCheckpoint.user_id == user_id,
                    DestinationCheckpoint.status == 'Active',
                    DestinationCheckpoint.target_date <= add_days(today, horizon))
            .order_by(DestinationCheckpoint.target_date.asc())
            .all())
    items = []
    for cp in rows:
        days_left = days_until(cp.target_date, today)
        company = cp.company
        items.append({
            'checkpoint_id': cp.id,
            'company': _company_label(company, 'Unknown company'),
            'company_id': cp.company_id,
            'held': cp.company_id in held,
            'metric': cp.metric,
            'expectation': cp.expectation,
            'target_date': cp.target_date.isoformat(),
            'days_until': days_left,
            'overdue': days_left < 0,
            'cite': ('checkpoint', cp.id,
                     f'{_company_label(company, "Checkpoint")} — {cp.metric}'),
        })
    return items


def _stalled_projects(user_id, now, stalled_after_days):
    cutoff = add_days(now, -stalled_after_days)
    items = []
    for project in ResearchProject.query.filter_by(user_id=user_id, status='active').all():
        last = project.last_worked_at or project.created_at
        last = ensure_timezone_aware(last) if last else None
        if last and last > cutoff:
            continue
        label = project.project_name or _company_label(project.company, 'Research project')
        items.append({
            'project_id': project.id,
            'company': _company_label(project.company, None),
            'company_id': project.company_id,
            'last_worked_at': last.date().isoformat() if last else None,
            'days_idle': days_between(last, now) if last else None,
            'cite': ('project', project.id, label),
        })
    # Longest idle first; never-dated projects sort last.
    items.sort(key=lambda i: -(i['days_idle'] if i['days_idle'] is not None else -1))
    return items


def _open_checklist_runs(user_id):
    items = []
    runs = (ChecklistAnalysis.query
            .filter_by(user_id=user_id, status='in_progress')
            .order_by(ChecklistAnalysis.start_date.desc())
            .all())
    for run in runs:
        questions = get_all_ordered_items_for_checklist(run.checklist_id)
        answered = {a.checklist_item_id for a in ChecklistAnswer.query.filter_by(
            checklist_analysis_id=run.id).all() if (a.answer_text or '').strip()}
        unanswered = sum(1 for q in questions if q.id not in answered)
        if not unanswered:
            continue
        checklist_name = run.checklist.name if run.checklist else None
        label = _company_label(run.company, 'Checklist run')
        if checklist_name:
            label = f'{label} — {checklist_name}'
        items.append({
            'analysis_id': run.id,
            'company': _company_label(run.company, None),
            'company_id': run.company_id,
            'checklist_name': checklist_name,
            'total_items': len(questions),
            'unanswered_items': unanswered,
            'cite': ('checklist', run.id, label),
        })
    return items


def _open_kill_sessions(user_id):
    items = []
    sessions = (KillSession.query
                .filter_by(user_id=user_id, completed_at=None)
                .order_by(KillSession.started_at.desc())
                .all())
    for session in sessions:
        total = session.checklist.criteria_count if session.checklist else 0
        answered = session.answers.filter(KillAnswer.passed.isnot(None)).count()
        unanswered = max(total - answered, 0)
        if not unanswered:
            continue
        idea_name = session.idea.name if session.idea else 'Idea'
        items.append({
            'kill_session_id': session.id,
            'idea': idea_name,
            'idea_id': session.idea_id,
            'kill_checklist': session.checklist.name if session.checklist else None,
            'total_criteria': total,
            'unanswered_criteria': unanswered,
            'cite': ('kill_session', session.id, f'{idea_name} — kill checklist'),
        })
    return items


def _thesis_drift(user_id):
    items = []
    for t in PortfolioIntelligenceService(user_id).get_thesis_reality_check():
        if t.status not in _DRIFT_STATUSES:
            continue
        items.append({
            'company': f'{t.company_name} ({t.company_ticker})',
            'company_id': t.company_id,
            'status': t.status,
            'expected_return_pct': t.expected_return,
            'expected_timeframe_months': t.expected_timeframe_months,
            'actual_return_pct': round(t.actual_return_pct, 1),
            'annualized_return_pct': round(t.annualized_return_pct, 1),
            'days_held': t.days_held,
            'cite': ('company', t.company_id, t.company_name),
        })
    return items


def build_agenda(user_id, horizon_days=None):
    """Everything waiting on the user, grouped by kind. All sections user-scoped.

    ``horizon_days`` falls back to the configured default and is clamped to the
    configured maximum.
    """
    settings = _settings(user_id)
    horizon = _clamp_horizon(horizon_days, settings)
    stalled_after = settings[ConfigKeys.AGENDA_STALLED_AFTER_DAYS]
    now = now_utc()
    today = now.date()
    return {
        'today': today.isoformat(),
        'horizon_days': horizon,
        'stalled_after_days': stalled_after,
        'checkpoints': _section(_checkpoints(user_id, today, horizon), settings),
        'stalled_projects': _section(
            _stalled_projects(user_id, now, stalled_after), settings),
        'open_checklist_runs': _section(_open_checklist_runs(user_id), settings),
        'open_kill_sessions': _section(_open_kill_sessions(user_id), settings),
        'thesis_drift': _section(_thesis_drift(user_id), settings),
    }
