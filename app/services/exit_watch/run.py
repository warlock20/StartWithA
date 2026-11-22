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

"""The exit-criteria watch monitor (#437): which rules to check, in what order, and the run summary."""

import logging

from flask import current_app

from app import db
from app.celery_tasks.base import TaskFailed
from app.models import AIInsight, Company, PortfolioPosition
from app.services import search_allowance
from app.services.ai_check.adapters import get_adapter
from app.services.exit_watch import ExitWatchError, check, episodes
from app.services.findings import active_must_exits_by_company
from app.services.monitor_registry import dedup_window, expiry_window
from app.utils.time_utils import datetime, ensure_timezone_aware, now_utc

LOG = logging.getLogger(__name__)
STATUS_ORDER = {'triggered': 0, 'at_risk': 1}
OTHER_RANK = 2
OLDEST = datetime(1970, 1, 1)


def _latest_insights(user_id, rule_ids):
    """Each rule's latest exit_criterion insight, active or not."""
    if not rule_ids:
        return {}
    rows = AIInsight.query.filter(
        AIInsight.user_id == user_id, AIInsight.context_type == check.CONTEXT_TYPE,
        AIInsight.context_id.in_(list(rule_ids)),
    ).order_by(AIInsight.created_at.asc(), AIInsight.id.asc()).all()
    return {row.context_id: row for row in rows}


def _checked_at(previous):
    if previous is None:
        return OLDEST
    raw = (previous.supporting_data or {}).get('checked_at')
    try:
        return ensure_timezone_aware(datetime.fromisoformat(raw)).replace(tzinfo=None)
    except (TypeError, ValueError):
        return ensure_timezone_aware(previous.created_at).replace(tzinfo=None)


def _order_key(item):
    previous = item['previous']
    status = (previous.supporting_data or {}).get('status') if previous is not None else None
    return (STATUS_ORDER.get(status, OTHER_RANK), _checked_at(previous), item['rule'].id)


def _rules_to_check(user):
    positions = PortfolioPosition.query.filter(
        PortfolioPosition.user_id == user.id, PortfolioPosition.is_active.is_(True),
        PortfolioPosition.total_shares > 0).all()
    by_company = {p.company_id: p for p in positions}
    rules_by_company = active_must_exits_by_company(user.id, list(by_company))
    companies = {c.id: c for c in Company.query.filter(Company.id.in_(list(by_company))).all()} if by_company else {}
    rules = [(rule, by_company[cid], companies.get(cid)) for cid, group in rules_by_company.items()
             for rule in group]
    latest = _latest_insights(user.id, [r.id for r, _, _ in rules])
    items = [{'rule': r, 'position': p, 'company': c, 'previous': latest.get(r.id)} for r, p, c in rules]
    return sorted(items, key=_order_key)


def _recent(previous, window, now):
    return (previous is not None and previous.is_active and previous.created_at is not None
            and ensure_timezone_aware(previous.created_at) >= ensure_timezone_aware(now) - window)


def run_exit_watch(user, monitor, adapter_factory=get_adapter, now=None):
    """Check every live exit rule on the user's held positions. Returns the run summary."""
    now = now or now_utc()
    episodes.resolve(user.id, now)
    db.session.commit()
    try:
        model_id = check.exit_watch_model(user.id)
    except ExitWatchError as exc:
        raise TaskFailed(str(exc))

    items = _rules_to_check(user)
    summary = {'kind': 'exit_watch', 'total': len(items), 'checked': 0, 'intact': 0, 'at_risk': 0,
               'triggered': 0, 'skipped_recent': 0, 'skipped_search_allowance': 0,
               'skipped_token_budget': 0, 'failed': 0, 'searches': 0, 'tokens': 0, 'cost': 0.0,
               'sources_unresolved': 0,
               'skipped_rule_ids': {'search_allowance': [], 'token_budget': []}}
    if not items:
        return summary

    adapter = adapter_factory(model_id)
    contact = current_app.config.get('AI_CHECK_FETCH_CONTACT')
    window, expires_after = dedup_window(monitor), expiry_window(monitor)
    out_of_tokens = False
    for item in items:
        rule, position, company, previous = item['rule'], item['position'], item['company'], item['previous']
        rule_id = rule.id
        if _recent(previous, window, now):
            summary['skipped_recent'] += 1
            continue
        if out_of_tokens or not user.can_use_ai_tokens(monitor.estimated_tokens):
            out_of_tokens = True
            summary['skipped_token_budget'] += 1
            summary['skipped_rule_ids']['token_budget'].append(rule_id)
            continue
        db.session.commit()  # check_rule rolls back on failure
        try:
            result = check.check_rule(
                user, rule, position, company, adapter, model_id, search_allowance.searches_left(user, now.replace(tzinfo=None)),
                previous, contact, expires_after, now=now)
            summary['tokens'] += result.tokens_in + result.tokens_out
            summary['cost'] += result.cost
            if result.needed_search_but_none_left:
                summary['skipped_search_allowance'] += 1
                summary['skipped_rule_ids']['search_allowance'].append(rule_id)
                continue
            episodes.record_check(rule, position, result.insight, result.status, now)
            db.session.commit()
        except Exception:
            LOG.exception('exit watch: checking rule %s failed', rule_id)
            db.session.rollback()
            summary['failed'] += 1
            continue
        summary['checked'] += 1
        if result.status in ('intact', 'at_risk', 'triggered'):
            summary[result.status] += 1
        summary['searches'] += result.searches
        summary['sources_unresolved'] += result.unresolved_sources
    return summary
