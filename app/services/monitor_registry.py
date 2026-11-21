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

"""Prompt kinds and the registry of user-configurable background monitors (#436)."""

from dataclasses import dataclass
from datetime import timedelta

# How a prompt is run: by the app itself, on user request, on an event, or on a schedule.
PROMPT_KINDS = ('internal', 'assistant', 'event', 'monitor')
FREQUENCIES = ('off', 'daily', 'weekly', 'monthly')
FREQUENCY_PERIODS = {
    'daily': timedelta(days=1),
    'weekly': timedelta(days=7),
    'monthly': timedelta(days=30),
}
DEDUP_SLACK = timedelta(hours=2)


@dataclass(frozen=True)
class Monitor:
    key: str
    label: str
    description: str
    prompts: tuple[tuple[str, str], ...]
    default_frequency: str
    allowed_frequencies: tuple[str, ...]
    feature: str | None
    estimated_tokens: int
    default_enabled: bool = True


MONITORS: dict[str, Monitor] = {
    'checkpoint_analysis': Monitor(
        key='checkpoint_analysis',
        label='Checkpoint analysis',
        description=(
            'Checks whether your active checkpoints that are due soon or overdue '
            'are on track, using your research.'
        ),
        prompts=(('checkpoint', 'checkpoint_analysis'),),
        default_frequency='weekly',
        allowed_frequencies=('daily', 'weekly', 'monthly'),
        feature=None,
        estimated_tokens=3000,
    ),
}


def get_monitor(key: str) -> Monitor | None:
    return MONITORS.get(key)


def dedup_window(monitor: Monitor) -> timedelta:
    """Shortest allowed period minus slack, so a run is never skipped as a duplicate."""
    periods = [FREQUENCY_PERIODS[f] for f in monitor.allowed_frequencies if f != 'off']
    return min(periods) - DEDUP_SLACK
