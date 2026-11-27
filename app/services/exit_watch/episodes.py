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

"""Trigger episodes for the exit-criteria watch (#437).

An episode is a must-exit rule going from intact to at_risk or triggered, plus what the user
did about it: sold (a trim counts), held anyway, or ignored. Insights stay the check history.

Nothing here commits; callers own the transaction. All datetimes are stored naive UTC.
"""

from typing import Optional

from app import db
from app.models import AIInsight, ExitRuleTrigger, JournalEntry, PortfolioPosition, Transaction
from app.models.portfolio import fifo_state_before
from app.services.exit_watch import CONTEXT_TYPE, STATUS_RANK, ExitWatchError
from app.services.findings import MUST_EXIT, project_id_for
from app.services.position_coverage import exit_plan_stale_days
from app.utils.time_utils import add_days, date, datetime, naive_utc, now_utc

GRACE_DAYS = 14

PENDING, SOLD, HELD, IGNORED = 'pending', 'sold', 'held', 'ignored'

NEEDS_REASON_MESSAGE = 'Say why you are holding through this exit rule.'
NO_EPISODE_MESSAGE = 'This exit rule has no open trigger to respond to.'


def _open_query(user_id: Optional[int] = None):
    query = ExitRuleTrigger.query.filter(ExitRuleTrigger.closed_at.is_(None))
    if user_id is not None:
        query = query.filter(ExitRuleTrigger.user_id == user_id)
    return query


def open_for_rules(rule_ids) -> dict:
    """The open episode of each rule id that has one: {rule_id: episode}."""
    rule_ids = list(rule_ids)
    if not rule_ids:
        return {}
    rows = _open_query().filter(ExitRuleTrigger.rule_id.in_(rule_ids)).order_by(ExitRuleTrigger.id).all()
    return {row.rule_id: row for row in rows}


def triggered_rules_on(user_id: int, company_id: int, on: date) -> list:
    """
    The must-exit rules that were triggered on a date, oldest episode first, one per rule:
    episodes whose worst status is triggered, opened by that day and not closed before it.
    Archived rules count: the rule was live when the user sold.
    """
    day_start = datetime(on.year, on.month, on.day)
    day_end = add_days(day_start, 1)
    episodes = ExitRuleTrigger.query.filter(
        ExitRuleTrigger.user_id == user_id,
        ExitRuleTrigger.company_id == company_id,
        ExitRuleTrigger.worst_status == 'triggered',
        ExitRuleTrigger.opened_at < day_end,
        db.or_(ExitRuleTrigger.closed_at.is_(None), ExitRuleTrigger.closed_at >= day_start),
    ).order_by(ExitRuleTrigger.opened_at, ExitRuleTrigger.id).all()
    rule_ids = list(dict.fromkeys(episode.rule_id for episode in episodes))
    rules = {rule.id: rule for rule in JournalEntry.query.filter(JournalEntry.id.in_(rule_ids))}
    return [rules[rule_id] for rule_id in rule_ids]


def _close(episode: ExitRuleTrigger, reason: str, now: datetime) -> None:
    episode.closed_at = naive_utc(now)
    episode.close_reason = reason


def _has_newer_dated_source(insight: Optional[AIInsight], held_at: datetime, now: datetime) -> bool:
    """A web source dated after the hold date and not in the future. App data and undated sources never count."""
    data = (insight.supporting_data if insight else None) or {}
    held_day = held_at.date()
    today = naive_utc(now).date()
    # A check that carried the previous evidence holds the old sources in web_sources (never new)
    # and its own finds in last_news_check.
    if data.get('evidence_carried'):
        found = (data.get('last_news_check') or {}).get('web_sources') or []
    else:
        found = data.get('web_sources') or []
    for source in found:
        published = (source or {}).get('published')
        if not published:
            continue
        try:
            day = date.fromisoformat(str(published)[:10])
        except ValueError:
            continue
        if held_day < day <= today:
            return True
    return False


def _realert(episode: ExitRuleTrigger, reason: str, now: datetime) -> None:
    episode.realerted_at = naive_utc(now)
    episode.realert_reason = reason


def _price_at_open(insight: Optional[AIInsight], position) -> tuple:
    """(price, currency) for a new episode: the check snapshot's price, else the position's."""
    snapshot = ((insight.supporting_data if insight else None) or {}).get('snapshot') or []
    for item in snapshot:
        if item.get('field') == 'price' and item.get('value') is not None:
            unit = item.get('unit')
            currency = unit if isinstance(unit, str) and len(unit) == 3 else None
            return item['value'], currency or (position.currency if position else None)
    if position is None:
        return None, None
    return position.current_price, position.currency


def record_check(rule, position, insight, status: str, now: datetime) -> Optional[ExitRuleTrigger]:
    """Fold one check result into the rule's episode. Does not commit.

    No open episode and a non-intact status opens one (price from the check's snapshot, else the
    position). An intact
    status closes the open episode. A status worse than the episode's previous status raises
    worst_status as needed and re-alerts a held or sold (trimmed) episode; a held episode also
    re-alerts when the check cites a web source dated after the hold. Returns the episode
    touched, or None.
    """
    episode = open_for_rules([rule.id]).get(rule.id)
    if episode is None:
        if status == 'intact':
            return None
        price, currency = _price_at_open(insight, position)
        episode = ExitRuleTrigger(
            user_id=rule.user_id, company_id=rule.company_id, rule_id=rule.id,
            opened_at=naive_utc(now), opening_insight_id=insight.id if insight else None,
            worst_status=status, current_status=status, response=PENDING,
            price_at_open=price, price_currency=currency,
            sold_after_hold=False,
        )
        db.session.add(episode)
        db.session.flush()
        return episode

    previous = episode.current_status
    if status == 'intact':
        episode.current_status = status
        _close(episode, 'intact', now)
        return episode

    worse = STATUS_RANK.get(status, 0) > STATUS_RANK.get(previous, 0)
    if STATUS_RANK.get(status, 0) > STATUS_RANK.get(episode.worst_status, 0):
        episode.worst_status = status
    episode.current_status = status
    if worse and episode.response in (HELD, SOLD):
        _realert(episode, 'worse', now)
    elif (episode.response == HELD and episode.held_at is not None and episode.realerted_at is None
            and _has_newer_dated_source(insight, episode.held_at, now)):
        _realert(episode, 'new_source', now)
    return episode


def _apply_sales(episode: ExitRuleTrigger, sells: list, now: datetime) -> None:
    """Update response and sold_pct from the company's SELLs (date, id order).

    While the response is pending, ignored or sold, the qualifying sales are those dated on or
    after the opening day: up to GRACE_DAYS later, or without an end once the episode was ever
    ignored. sold_pct is recomputed from all of them each time (capped at 100). After a hold,
    any later sale only sets sold_after_hold.
    """
    now_db = naive_utc(now)
    start = episode.opened_at.date()
    end = add_days(start, GRACE_DAYS)
    if episode.response in (PENDING, IGNORED, SOLD):
        if (episode.response == PENDING and now_db >= add_days(episode.opened_at, GRACE_DAYS)
                and not any(start <= s.date <= end for s in sells)):
            episode.response = IGNORED
            episode.ignored_at = now_db
        qualifying = [s for s in sells
                      if s.date >= start and (episode.ignored_at is not None or s.date <= end)]
        if qualifying:
            before = fifo_state_before(qualifying[0]).total_shares
            sold_qty = sum(s.quantity or 0 for s in qualifying)
            episode.sold_pct = min(100.0, round(sold_qty / before * 100, 2)) if before > 0 else None
            if episode.response != SOLD:
                episode.response = SOLD
                episode.responded_at = now_db
    elif episode.response == HELD and episode.held_at is not None:
        if any(s.date >= episode.held_at.date() for s in sells):
            episode.sold_after_hold = True


def _sells_for(user_id: int, company_ids) -> dict:
    """SELL transactions of the given companies, {company_id: [oldest first]}."""
    sells = {}
    if not company_ids:
        return sells
    rows = (Transaction.query
            .filter(Transaction.user_id == user_id, Transaction.company_id.in_(list(company_ids)),
                    Transaction.type == 'SELL')
            .order_by(Transaction.date, Transaction.id).all())
    for row in rows:
        sells.setdefault(row.company_id, []).append(row)
    return sells


def resolve(user_id: int, now: datetime) -> bool:
    """Bring the user's open episodes up to date from the rules and the transactions. Does not commit.

    Archived or missing rule closes the episode; sales set sold or sold_after_hold (see
    _apply_sales); a closed position closes the episode; a pending episode past GRACE_DAYS
    with no sale becomes ignored (and keeps alerting); a hold older than exit_plan_stale_days()
    with no re-alert since re-asks. Returns True when any episode changed, so a GET view
    commits only then.
    """
    open_episodes = _open_query(user_id).order_by(ExitRuleTrigger.id).all()
    if not open_episodes:
        return False
    company_ids = {e.company_id for e in open_episodes}
    rules = {r.id: r for r in JournalEntry.query.filter(
        JournalEntry.id.in_({e.rule_id for e in open_episodes})).all()}
    positions = {p.company_id: p for p in PortfolioPosition.query.filter(
        PortfolioPosition.user_id == user_id, PortfolioPosition.company_id.in_(company_ids)).all()}
    sells = _sells_for(user_id, company_ids)
    now_db = naive_utc(now)
    stale_days = exit_plan_stale_days()
    for episode in open_episodes:
        rule = rules.get(episode.rule_id)
        if rule is None or rule.is_archived or rule.entry_type != MUST_EXIT:
            _close(episode, 'rule_archived', now)
            continue

        _apply_sales(episode, sells.get(episode.company_id, []), now)

        position = positions.get(episode.company_id)
        if position is None or not position.is_active:
            _close(episode, 'position_closed', now)
            continue

        if (episode.response == HELD and episode.held_at is not None
                and episode.realerted_at is None
                and now_db >= add_days(episode.held_at, stale_days)):
            _realert(episode, 'reask', now)
    return any(db.session.is_modified(episode) for episode in open_episodes)


def hold(user_id: int, rule_id: int, reason: str, now: datetime) -> ExitRuleTrigger:
    """Hold through the rule's open trigger ("Hold anyway" and "Still holding"). Does not commit.

    The first hold needs a reason; later ones may leave it empty. A typed reason is saved as a
    journal entry on the company and linked on the episode. Pending sales are applied first, so a
    sale between two holds is not missed; holding a sold (trimmed) episode is allowed and keeps
    sold_pct. Clears any re-alert, keeps ignored_at. A "Still holding" without a reason keeps
    the previous hold entry (and so the previous reason).
    """
    episode = _open_query(user_id).filter(ExitRuleTrigger.rule_id == rule_id).first()
    rule = db.session.get(JournalEntry, rule_id) if episode else None
    if episode is None or rule is None or rule.user_id != user_id:
        raise ExitWatchError(NO_EPISODE_MESSAGE)
    _apply_sales(episode, _sells_for(user_id, [episode.company_id]).get(episode.company_id, []), now)
    reason = (reason or '').strip()
    if not reason and episode.held_at is None:
        raise ExitWatchError(NEEDS_REASON_MESSAGE)

    if reason:
        entry = JournalEntry(
            user_id=user_id, company_id=episode.company_id,
            project_id=project_id_for(user_id, episode.company_id),
            entry_type='observation', title=f'Holding through exit rule: {rule.title}'[:200],
            content=reason, source='exit_watch',
        )
        db.session.add(entry)
        db.session.flush()
        episode.hold_entry_id = entry.id

    now_db = naive_utc(now)
    episode.response = HELD
    episode.held_at = now_db
    episode.responded_at = now_db
    episode.realerted_at = None
    episode.realert_reason = None
    return episode


def latest_insights(user_id: int, rule_ids) -> dict:
    """The newest exit-criterion insight of each rule id: {rule_id: insight} (one DISTINCT ON query)."""
    rule_ids = list(rule_ids)
    if not rule_ids:
        return {}
    rows = (AIInsight.query
            .filter(AIInsight.user_id == user_id, AIInsight.context_type == CONTEXT_TYPE,
                    AIInsight.context_id.in_(rule_ids))
            .distinct(AIInsight.context_id)
            .order_by(AIInsight.context_id, AIInsight.created_at.desc(), AIInsight.id.desc()).all())
    return {row.context_id: row for row in rows}


def is_alerting(episode: ExitRuleTrigger, insight: Optional[AIInsight], now: datetime) -> bool:
    """Whether an open episode should alert: fresh latest check, and pending/ignored or re-alerted.

    The rule's latest insight must be active and unexpired (a stale check never alerts).
    """
    if insight is None or not insight.is_active:
        return False
    if insight.expires_at is not None and naive_utc(insight.expires_at) <= naive_utc(now):
        return False
    return episode.response in (PENDING, IGNORED) or episode.realerted_at is not None


def alerting(user_id: int, now: Optional[datetime] = None) -> list:
    """Open episodes that should alert now (see is_alerting), for live must-exit rules only."""
    now = now or now_utc()
    episodes = _open_query(user_id).order_by(ExitRuleTrigger.id).all()
    if not episodes:
        return []
    rule_ids = [e.rule_id for e in episodes]
    live = {r.id for r in JournalEntry.query.filter(
        JournalEntry.id.in_(rule_ids), JournalEntry.is_archived.is_(False),
        JournalEntry.entry_type == MUST_EXIT).all()}
    latest = latest_insights(user_id, rule_ids)
    return [e for e in episodes if e.rule_id in live and is_alerting(e, latest.get(e.rule_id), now)]
