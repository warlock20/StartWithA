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

"""Turning the edit form into ai_context, and reading it back."""

RUBRIC_KEYS = ('satisfied', 'not_satisfied', 'needs_attention')


def _clean(value):
    return (value or '').strip()


def ai_context_from_form(form):
    """Build the ai_context dict from the edit form. None when the method is empty."""
    method = _clean(form.get('ai_method'))
    if not method:
        return None
    links = [line.strip() for line in (form.get('ai_source_links') or '').splitlines()]
    return {
        'method': method,
        'where_to_look': _clean(form.get('ai_where_to_look')),
        'worked_example': _clean(form.get('ai_worked_example')),
        'verdict_rubric': {key: _clean(form.get(f'ai_rubric_{key}')) for key in RUBRIC_KEYS},
        'source_links': [link for link in links if link.startswith(('http://', 'https://'))],
    }


def has_ai_context(ctx):
    return bool(ctx and _clean(ctx.get('method')))


def ai_context_status(ctx):
    """'none', 'method_only' or 'complete' (method, where to look, example, all three rubric lines)."""
    if not has_ai_context(ctx):
        return 'none'
    rubric = ctx.get('verdict_rubric') or {}
    complete = (_clean(ctx.get('where_to_look')) and _clean(ctx.get('worked_example'))
                and all(_clean(rubric.get(key)) for key in RUBRIC_KEYS))
    return 'complete' if complete else 'method_only'


def context_snapshot(item):
    """The question and its AI context, frozen onto a run when it starts."""
    return {**(item.ai_context or {}), 'question': item.text}
