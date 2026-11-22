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

"""Exit-criteria watch (#437): periodic checks of must-exit rules for held positions."""


class ExitWatchError(Exception):
    """A user-facing failure: the message is shown in the UI as is."""


CONTEXT_TYPE = 'exit_criterion'  # AIInsight.context_type of a rule check; context_id is the rule id
STATUS_LABELS = {'intact': 'Intact', 'at_risk': 'At risk', 'triggered': 'Triggered'}
STATUS_RANK = {'intact': 0, 'at_risk': 1, 'triggered': 2}
