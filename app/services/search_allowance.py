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

"""Monthly web-search allowance for background AI (#437).

Counted from PromptUsageLog.web_searches, not from a counter. The window follows
the token budget; start is exclusive, end inclusive, all naive UTC like the DB:
- reset date in the future: (reset - 30 days, reset]
- reset date overdue (it only runs when tokens are next used): rolled forward in
  30-day steps to the period containing now, (reset + k*30d, reset + (k+1)*30d]
- no reset date: the calendar month (UTC)
"""

import math

from sqlalchemy import func

from app import db
from app.models import ResearchSettings
from app.models.prompt_management import PromptUsageLog
from app.services.config_service import ConfigKeys, get_config
from app.utils.time_utils import ensure_timezone_aware, now_utc, timedelta, timezone

DEFAULT_ALLOWANCE = 150
DEFAULT_ALLOWANCE_MAX = 500
MAX_ALLOWANCE_CEILING = 10000  # keep in step with max_value in the seeding migration
WINDOW_DAYS = 30
# Prompts whose web searches count against the allowance. AI check has its own limit.
BACKGROUND_SEARCH_PROMPTS = ('exit_criteria_check',)


def _naive_utc_now():
    return now_utc().replace(tzinfo=None)


def allowance_window(user, now=None):
    """(start, end) of the user's current month: start exclusive, end inclusive."""
    now = now or _naive_utc_now()
    reset = user.ai_tokens_reset_date
    if reset is not None:
        reset = ensure_timezone_aware(reset).astimezone(timezone.utc).replace(tzinfo=None)  # in-session values are aware until reloaded
        if reset <= now:
            # Reset overdue (it only runs when tokens are next used): roll forward in 30-day
            # steps to the period containing now.
            step = timedelta(days=WINDOW_DAYS)
            periods_elapsed = -((reset - now) // step)  # ceil((now - reset) / step)
            start = reset + max(0, periods_elapsed - 1) * step
            return start, start + step
        return reset - timedelta(days=WINDOW_DAYS), reset
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def allowance_max():
    """Admin ceiling for a user's allowance; junk or out-of-range config falls back to the default."""
    value = get_config(ConfigKeys.BACKGROUND_SEARCH_ALLOWANCE_MAX, default=DEFAULT_ALLOWANCE_MAX)
    try:
        ceiling = float(value)
    except (TypeError, ValueError):
        return DEFAULT_ALLOWANCE_MAX
    if not math.isfinite(ceiling) or not 0 <= ceiling <= MAX_ALLOWANCE_CEILING:
        return DEFAULT_ALLOWANCE_MAX
    return int(ceiling)


def _settings(user):
    return ResearchSettings.query.filter_by(user_id=user.id).first()


def user_allowance(user):
    """The user's monthly allowance: stored value clamped to [0, admin max], NULL means the default."""
    settings = _settings(user)
    stored = settings.background_search_allowance if settings else None
    if stored is None:
        stored = DEFAULT_ALLOWANCE
    return max(0, min(stored, allowance_max()))


def searches_used(user, now=None):
    start, end = allowance_window(user, now)
    total = db.session.query(func.coalesce(func.sum(PromptUsageLog.web_searches), 0)).filter(
        PromptUsageLog.user_id == user.id,
        PromptUsageLog.prompt_name.in_(BACKGROUND_SEARCH_PROMPTS),
        PromptUsageLog.created_at > start,
        PromptUsageLog.created_at <= end,
    ).scalar()
    return int(total)


def searches_left(user, now=None):
    return max(0, user_allowance(user) - searches_used(user, now))


def allowance_status(user, now=None):
    used = searches_used(user, now)
    allowance = user_allowance(user)
    return {
        'used': used,
        'allowance': allowance,
        'remaining': max(0, allowance - used),
        'resets_at': allowance_window(user, now)[1],
    }


def set_allowance(user, raw):
    """Store the user's allowance. Raises ValueError with a user-facing message. Does not commit."""
    ceiling = allowance_max()
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        raise ValueError('Enter a whole number of searches.') from None
    if not 0 <= value <= ceiling:
        raise ValueError(f'The allowance must be between 0 and {ceiling} searches a month.')
    settings = _settings(user)
    if settings is None:
        settings = ResearchSettings(user_id=user.id)
        db.session.add(settings)
    settings.background_search_allowance = value
    return value
