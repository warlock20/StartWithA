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

"""Letter grades for 0-100 quality scores."""

from app.constants import GRADE_A_THRESHOLD, GRADE_B_THRESHOLD, GRADE_C_THRESHOLD, GRADE_D_THRESHOLD


def score_to_grade(score: float) -> str:
    """Convert a 0-100 score to a letter grade (A-F)."""
    if score >= GRADE_A_THRESHOLD:
        return 'A'
    if score >= GRADE_B_THRESHOLD:
        return 'B'
    if score >= GRADE_C_THRESHOLD:
        return 'C'
    if score >= GRADE_D_THRESHOLD:
        return 'D'
    return 'F'
