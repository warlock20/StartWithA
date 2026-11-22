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

"""What the UI shows for each must-exit rule: latest check, sources, and the user's response (#437)."""

from typing import Optional
from urllib.parse import urlparse

from app.models import JournalEntry
from app.services.exit_watch import episodes
from app.utils.time_utils import date, now_utc

STATUS_LABELS = {'intact': 'Intact', 'at_risk': 'At risk', 'triggered': 'Triggered'}
DATE_FORMAT = '%b %d, %Y'


def _display(value) -> Optional[str]:
    return value.strftime(DATE_FORMAT) if value else None


def _safe_url(url) -> bool:
    """Only http(s) links with a host are rendered as hrefs (no javascript: or data: URLs)."""
    try:
        parsed = urlparse(str(url or ''))
    except ValueError:
        return False
    return parsed.scheme in ('http', 'https') and bool(parsed.hostname)


def _published_display(value) -> Optional[str]:
    try:
        return date.fromisoformat(str(value)[:10]).strftime(DATE_FORMAT)
    except ValueError:
        return None


def _sources(data: dict) -> list:
    return [{'url': s.get('url'), 'title': s.get('title') or s.get('url'),
             'published': s.get('published'), 'published_display': _published_display(s.get('published')),
             'date_source': s.get('date_source')}
            for s in data.get('web_sources') or [] if _safe_url(s.get('url'))]


def rule_states(user_id: int, rule_ids, now=None) -> dict:
    """Per rule id with a check or an open episode: status, summary, sources and the episode. One query per table.

    Rules never checked and without an episode are left out. 'expired' is True when the latest
    check is inactive or past its expiry ("Not checked since <date>").
    """
    rule_ids = list(rule_ids)
    if not rule_ids:
        return {}
    now_db = episodes._naive(now or now_utc())
    latest = episodes.latest_insights(user_id, rule_ids)
    open_episodes = episodes.open_for_rules(rule_ids)
    open_episodes = {rid: e for rid, e in open_episodes.items() if e.user_id == user_id}
    hold_ids = [e.hold_entry_id for e in open_episodes.values() if e.hold_entry_id]
    reasons = {}
    if hold_ids:
        reasons = {e.id: e.content for e in JournalEntry.query.filter(
            JournalEntry.id.in_(hold_ids), JournalEntry.user_id == user_id).all()}

    states = {}
    for rule_id in rule_ids:
        insight, episode = latest.get(rule_id), open_episodes.get(rule_id)
        if insight is None and episode is None:
            continue
        data = (insight.supporting_data if insight else None) or {}
        status = data.get('status') or (episode.current_status if episode else 'intact')
        expired = insight is None or not insight.is_active or (
            insight.expires_at is not None and episodes._naive(insight.expires_at) <= now_db)
        checked = insight.created_at if insight else None
        state = {
            'status': status,
            'status_label': STATUS_LABELS.get(status, status),
            'checked_at': checked.isoformat() if checked else None,
            'checked_display': _display(checked),
            'summary': data.get('summary') or '',
            'no_evidence': bool(data.get('no_evidence')),
            'sources': _sources(data),
            'expired': expired,
            'episode': None,
        }
        if episode is not None:
            alerting = episodes.is_alerting(episode, insight, now_db)
            state['episode'] = {
                'response': episode.response,
                'opened_at': episode.opened_at.isoformat() if episode.opened_at else None,
                'held_at': episode.held_at.isoformat() if episode.held_at else None,
                'held_display': _display(episode.held_at),
                'hold_reason': reasons.get(episode.hold_entry_id),
                'realert_reason': episode.realert_reason,
                'alerting': alerting,
            }
        states[rule_id] = state
    return states
