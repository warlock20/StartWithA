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

"""Position coverage warnings: which open positions lack the plans they need."""

import math

from app.services.config_service import ConfigKeys, get_config

DEFAULT_EXIT_PLAN_STALE_DAYS = 90
MAX_EXIT_PLAN_STALE_DAYS = 3650  # keep in step with max_value in the seeding migration


def exit_plan_stale_days() -> int:
    """Days without a rule review/update after which an exit plan is stale.

    Anything that is not a number in [1, MAX_EXIT_PLAN_STALE_DAYS] (including
    inf/nan) falls back to the default; decimals are truncated.
    """
    value = get_config(ConfigKeys.EXIT_PLAN_STALE_DAYS, default=DEFAULT_EXIT_PLAN_STALE_DAYS)
    try:
        days = float(value)
    except (TypeError, ValueError):
        return DEFAULT_EXIT_PLAN_STALE_DAYS
    if not math.isfinite(days) or not 1 <= days <= MAX_EXIT_PLAN_STALE_DAYS:
        return DEFAULT_EXIT_PLAN_STALE_DAYS
    return int(days)
