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

import zlib

from sqlalchemy.exc import IntegrityError

from app import db
from app.features import user_has_feature
from app.models.user_monitor_setting import UserMonitorSetting
from app.services.monitor_registry import FREQUENCY_PERIODS, Monitor, get_monitor
from app.utils.time_utils import datetime, ensure_timezone_aware, now_utc, timedelta, timezone

EPOCH = datetime(2024, 1, 1, tzinfo=timezone.utc)
_HOUR = timedelta(hours=1)


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
