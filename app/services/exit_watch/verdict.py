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

"""Verdict rules for one exit-criteria check: what status the rule gets after the model answers."""

STATUS_RANK = {'intact': 0, 'at_risk': 1, 'triggered': 2}


def decide(model_status, changed, web_ids, app_ids, previous_status):
    """Status is where the rule stands now, and it only moves on evidence.

    Returns status, the model's own status, whether it claimed a non-intact status without
    evidence, and whether the previous status was kept.
    """
    has_evidence = bool(web_ids or app_ids)
    no_evidence = model_status != 'intact' and not has_evidence

    def result(status, kept=False):
        return {'status': status, 'model_status': model_status,
                'no_evidence': no_evidence, 'kept_previous': kept}

    if (previous_status in STATUS_RANK and has_evidence
            and STATUS_RANK.get(model_status, 0) > STATUS_RANK[previous_status]):
        changed = True
    if previous_status in ('at_risk', 'triggered') and (not changed or not has_evidence):
        return result(previous_status, kept=True)
    if no_evidence:
        return result('intact')
    return result(model_status)
