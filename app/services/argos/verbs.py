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

"""
Composer verbs — the stance a question is asked in.

Picking a verb prefixes the composer with its stance; the user names the subject.
The combined text goes to the companion agent as an ordinary question, so a verb
decides framing, not capability — it can only ask for what a typed question could
already get.

The stance text reaches the model, so it lives in the prompt YAML
(``companion/verbs.yaml``) with the rest of the phrasing, and can be reworded
without touching code. Verbs carry no canned questions on purpose: a stored
library of guesses goes stale and stops matching what the user actually has.
"""

from app.services.ai.prompt_service import prompt_service

_REQUIRED = ('key', 'label', 'stance', 'placeholder')


def list_verbs():
    """Verbs for the composer, as ``{key, label, icon, stance, placeholder}``.

    Malformed entries are skipped rather than raising: a typo in the YAML should
    cost one verb, not the whole rail.
    """
    data = prompt_service.get_prompt_data('companion', 'verbs')
    verbs = []
    for entry in data.get('verbs') or []:
        if not isinstance(entry, dict):
            continue
        if any(not str(entry.get(field) or '').strip() for field in _REQUIRED):
            continue
        verbs.append({
            'key': str(entry['key']).strip(),
            'label': str(entry['label']).strip(),
            'icon': str(entry.get('icon') or 'bi-chevron-right').strip(),
            'stance': ' '.join(str(entry['stance']).split()),
            'placeholder': str(entry['placeholder']).strip(),
        })
    return verbs
