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

"""Per-user schedule for background monitors: slot math and settings validation (#436)."""

import logging
import math
import zlib

from sqlalchemy.exc import IntegrityError

from app import db
from app.celery_tasks.tasks_monitors import MONITOR_RUN_SOFT_LIMIT
from app.features import user_has_feature
from app.models import BackgroundTask, User
from app.models.user_monitor_setting import UserMonitorSetting
from app.services.background_tasks import BackgroundTaskService
from app.services.monitor_registry import (
    EVENTS, FREQUENCY_PERIODS, MONITORS, Monitor, get_event, get_monitor,
)
from app.utils.time_utils import datetime, ensure_timezone_aware, now_utc, timedelta, timezone

logger = logging.getLogger(__name__)

EPOCH = datetime(2024, 1, 1, tzinfo=timezone.utc)
_HOUR = timedelta(hours=1)
MONITOR_RUN_STALL_SECONDS = MONITOR_RUN_SOFT_LIMIT * 2
RUN_NOW_COOLDOWN = timedelta(minutes=10)
SETTINGS_LINK_TEXT = 'Settings → Background AI'
OFF_MESSAGE = '{label} is turned off. Turn it on in {settings}.'


class MonitorSettingError(Exception):
    """Invalid monitor setting. The message is shown to the user."""


def _floor_hour(dt: datetime) -> datetime:
    return dt.replace(minute=0, second=0, microsecond=0)


def effective(monitor: Monitor, row: UserMonitorSetting | None) -> tuple[bool, str]:
    """(enabled, frequency) with NULL or missing values falling back to registry defaults."""
    enabled = monitor.default_enabled if row is None or row.enabled is None else row.enabled
    frequency = monitor.default_frequency if row is None or row.frequency is None else row.frequency
    return enabled, frequency


def is_active(monitor: Monitor, row: UserMonitorSetting | None) -> bool:
    enabled, frequency = effective(monitor, row)
    return enabled and frequency != 'off'


def next_slot(user_id: int, monitor_key: str, frequency: str, after: datetime,
              inclusive: bool) -> datetime:
    """The user's next run slot, on the hour, stable per (user, monitor, frequency).

    Slots are EPOCH + offset hours + k * period. inclusive=True returns the first slot
    at or after the hour containing `after`; inclusive=False the first slot after `after`.
    """
    period = FREQUENCY_PERIODS[frequency]
    period_h = period // _HOUR
    offset = zlib.crc32(f'{user_id}:{monitor_key}'.encode()) % period_h
    base = EPOCH + timedelta(hours=offset)
    after = ensure_timezone_aware(after).astimezone(timezone.utc)
    if inclusive:
        k = -((base - _floor_hour(after)) // period)  # ceil((floor_hour(after) - base) / period)
    else:
        k = (after - base) // period + 1
    return base + k * period


def get_row(user_id: int, monitor_key: str) -> UserMonitorSetting | None:
    return UserMonitorSetting.query.filter_by(user_id=user_id, monitor_key=monitor_key).first()


def get_or_create_row(user_id: int, monitor_key: str) -> UserMonitorSetting:
    row = get_row(user_id, monitor_key)
    if row is None:
        row = UserMonitorSetting(user_id=user_id, monitor_key=monitor_key)
        try:
            with db.session.begin_nested():
                db.session.add(row)
        except IntegrityError:
            # A concurrent request created it first (double submit): use theirs.
            row = get_row(user_id, monitor_key)
    return row


def update_setting(user, monitor_key: str, enabled: bool, frequency: str,
                   now: datetime | None = None) -> UserMonitorSetting:
    """Validate and store a user's choice, rescheduling when it changes the cadence."""
    monitor = get_monitor(monitor_key)
    if monitor is None:
        raise MonitorSettingError('Unknown monitor.')
    if monitor.feature and not user_has_feature(user, monitor.feature):
        raise MonitorSettingError(f'{monitor.label} is available on the Pro plan.')
    if frequency not in monitor.allowed_frequencies:
        allowed = list(monitor.allowed_frequencies)
        if len(allowed) > 1:
            choices = ', '.join(allowed[:-1]) + ' or ' + allowed[-1]
        else:
            choices = allowed[0]
        raise MonitorSettingError(f'Choose {choices}.')

    now = now or now_utc()
    row = get_or_create_row(user.id, monitor_key)
    was_enabled, was_frequency = effective(monitor, row)
    row.enabled = enabled
    row.frequency = frequency
    if frequency != was_frequency or (enabled and not was_enabled):
        row.next_run_at = next_slot(user.id, monitor_key, frequency, now, inclusive=False)
    db.session.commit()
    return row


def _event_locked(user, event) -> bool:
    return bool(event.feature and not user_has_feature(user, event.feature))


def event_enabled(user, key: str) -> bool:
    """Whether the user's event check may run. KeyError for an unknown key."""
    event = EVENTS[key]
    if _event_locked(user, event):
        return False
    row = get_row(user.id, key)
    return event.default_enabled if row is None or row.enabled is None else row.enabled


def update_event_setting(user, key: str, enabled: bool) -> UserMonitorSetting:
    """Switch an event check on or off. Only `enabled` is stored; there is no schedule."""
    event = get_event(key)
    if event is None:
        raise MonitorSettingError('Unknown check.')
    if _event_locked(user, event):
        raise MonitorSettingError(f'{event.label} is available on the Pro plan.')
    row = get_or_create_row(user.id, key)
    row.enabled = enabled
    db.session.commit()
    return row


def event_rows(user) -> list[dict]:
    """One settings-page row per event check, in registry order."""
    return [{
        'key': event.key,
        'label': event.label,
        'description': event.description,
        'enabled': event_enabled(user, event.key),
        'locked': _event_locked(user, event),
    } for event in EVENTS.values()]


def _naive_utc(dt: datetime) -> datetime:
    """The naive UTC form the DateTime columns store."""
    return ensure_timezone_aware(dt).astimezone(timezone.utc).replace(tzinfo=None)


def _dispatch_one(user, monitor: Monitor, row: UserMonitorSetting | None, now: datetime) -> str:
    """Decide and apply one user's step for one monitor. Returns the outcome name."""
    if not is_active(monitor, row):
        return 'inactive'
    if monitor.feature and not user_has_feature(user, monitor.feature):
        return 'locked'

    _, frequency = effective(monitor, row)
    if row is None:
        row = get_or_create_row(user.id, monitor.key)
    if row.next_run_at is None:
        row.next_run_at = _naive_utc(next_slot(user.id, monitor.key, frequency, now, inclusive=True))
        # Commit the slot even when it is due now: a broker failure below rolls back,
        # and recomputing an hour later would jump a whole period.
        db.session.commit()
        if ensure_timezone_aware(row.next_run_at) > now:
            return 'scheduled'
    elif ensure_timezone_aware(row.next_run_at) > now:
        return 'waiting'

    next_run_at = _naive_utc(next_slot(user.id, monitor.key, frequency, now, inclusive=False))
    if not user.can_use_ai_tokens(monitor.estimated_tokens):
        row.next_run_at = next_run_at
        db.session.commit()
        return 'over_budget'
    _fail_stalled_runs(user.id, monitor.key)
    # Enqueue before touching the schedule: start_monitor_run commits, so advancing
    # first would skip the user for a whole period if the broker is down. A failure
    # now leaves the schedule alone and the next hourly dispatch retries. A failed
    # final commit can run the monitor twice, which the monitor's dedup window absorbs.
    BackgroundTaskService.start_monitor_run(user.id, monitor.key)
    row.last_run_at = _naive_utc(now)
    row.next_run_at = next_run_at
    db.session.commit()
    return 'enqueued'


def _fail_stalled_runs(user_id: int, monitor_key: str) -> None:
    """Fail an in-flight run whose worker died, so it cannot block every later dispatch."""
    latest = (BackgroundTask.query
              .filter(BackgroundTask.user_id == user_id,
                      BackgroundTask.task_type == f'monitor:{monitor_key}',
                      BackgroundTask.status.in_(('pending', 'running')))
              .order_by(BackgroundTask.created_at.desc()).first())
    if latest is not None:
        BackgroundTaskService.fail_if_stalled(latest.id, user_id, MONITOR_RUN_STALL_SECONDS)


def _minutes(delta: timedelta) -> int:
    return max(1, math.ceil(delta.total_seconds() / 60))


def _last_task(user_id: int, monitor_key: str) -> dict | None:
    """The user's latest run of a monitor, with a dead in-flight run reconciled first."""
    _fail_stalled_runs(user_id, monitor_key)
    task = (BackgroundTask.query
            .filter_by(user_id=user_id, task_type=f'monitor:{monitor_key}')
            .order_by(BackgroundTask.created_at.desc()).first())
    if task is None:
        return None
    return {
        'status': task.status,
        'error': task.error_message,
        'created_at': task.created_at,
        'completed_at': task.completed_at,
        'result': BackgroundTaskService.stored_result(task),
    }


def monitor_rows(user, now: datetime | None = None) -> list[dict]:
    """One settings-page row per registry monitor, in registry order."""
    now = ensure_timezone_aware(now or now_utc())
    rows = []
    for monitor in MONITORS.values():
        row = get_row(user.id, monitor.key)
        enabled, frequency = effective(monitor, row)
        active = is_active(monitor, row)
        locked = bool(monitor.feature and not user_has_feature(user, monitor.feature))
        if not active or locked or not user.ai_consent_given:
            next_run_at = None
        elif row is not None and row.next_run_at is not None:
            next_run_at = row.next_run_at
        else:
            next_run_at = _naive_utc(next_slot(user.id, monitor.key, frequency, now, inclusive=True))
        rows.append({
            'key': monitor.key,
            'label': monitor.label,
            'description': monitor.description,
            'locked': locked,
            'enabled': enabled,
            'frequency': frequency,
            'allowed_frequencies': monitor.allowed_frequencies,
            'default_frequency': monitor.default_frequency,
            'uses_default_frequency': row is None or row.frequency is None,
            'last_run_at': row.last_run_at if row is not None else None,
            'next_run_at': next_run_at,
            'last_task': _last_task(user.id, monitor.key),
        })
    return rows


def run_now(user, monitor_key: str, now: datetime | None = None) -> str:
    """Queue a run on the user's request. Returns the task id."""
    monitor = get_monitor(monitor_key)
    if monitor is None:
        raise MonitorSettingError('Unknown monitor.')
    if monitor.feature and not user_has_feature(user, monitor.feature):
        raise MonitorSettingError(f'{monitor.label} is available on the Pro plan.')
    if not user.ai_consent_given:
        raise MonitorSettingError('Turn on AI features in Settings → AI first.')
    if not user.can_use_ai_tokens(monitor.estimated_tokens):
        raise MonitorSettingError('Not enough AI tokens left this month to run it.')

    now = ensure_timezone_aware(now or now_utc())
    naive_now = _naive_utc(now)
    task_type = f'monitor:{monitor_key}'
    _fail_stalled_runs(user.id, monitor_key)
    in_flight = (BackgroundTask.query
                 .filter(BackgroundTask.user_id == user.id, BackgroundTask.task_type == task_type,
                         BackgroundTask.status.in_(('pending', 'running'))).first())
    if in_flight is not None:
        raise MonitorSettingError('It is already running. Refresh in a minute to see the result.')
    latest = (BackgroundTask.query
              .filter(BackgroundTask.user_id == user.id, BackgroundTask.task_type == task_type,
                      BackgroundTask.status != 'failed')
              .order_by(BackgroundTask.created_at.desc()).first())
    elapsed = max(naive_now - latest.created_at, timedelta(0)) if latest is not None else None
    if elapsed is not None and elapsed < RUN_NOW_COOLDOWN:
        raise MonitorSettingError(
            f'It ran {_minutes(elapsed)} min ago. '
            f'Try again in {_minutes(RUN_NOW_COOLDOWN - elapsed)} min.')

    task_id = BackgroundTaskService.start_monitor_run(user.id, monitor_key)
    row = get_or_create_row(user.id, monitor_key)
    row.last_run_at = naive_now
    db.session.commit()
    return task_id


def dispatch_due_monitors(now: datetime | None = None) -> dict:
    """Queue every monitor run that is due, for users who consented to AI features.

    Commits after each user so one user's failure cannot undo the others.
    """
    now = ensure_timezone_aware(now or now_utc())
    counts = {'enqueued': 0, 'scheduled': 0, 'over_budget': 0, 'locked': 0, 'inactive': 0}
    user_ids = [uid for (uid,) in db.session.query(User.id)
                .filter(User.ai_consent_given.is_(True)).order_by(User.id)]

    for monitor in MONITORS.values():
        rows = {r.user_id: r for r in UserMonitorSetting.query.filter_by(monitor_key=monitor.key)}
        for user_id in user_ids:
            try:
                user = db.session.get(User, user_id)
                outcome = _dispatch_one(user, monitor, rows.get(user_id), now)
            except Exception:
                logger.exception('Monitor dispatch failed for user %s, monitor %s', user_id, monitor.key)
                db.session.rollback()
                rows = {r.user_id: r for r in UserMonitorSetting.query.filter_by(monitor_key=monitor.key)}
                continue
            if outcome in counts:
                counts[outcome] += 1
    return counts
