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
    """Build the ai_context dict from the edit form. None only when every field is empty, so
    typed guidance (where to look, example, rubric, links) survives an empty Method; the run
    stays gated on Method by has_ai_context."""
    links = [line.strip() for line in (form.get('ai_source_links') or '').splitlines()]
    ctx = {
        'method': _clean(form.get('ai_method')),
        'where_to_look': _clean(form.get('ai_where_to_look')),
        'worked_example': _clean(form.get('ai_worked_example')),
        'verdict_rubric': {key: _clean(form.get(f'ai_rubric_{key}')) for key in RUBRIC_KEYS},
        'source_links': [link for link in links if link.startswith(('http://', 'https://'))],
    }
    filled = (ctx['method'] or ctx['where_to_look'] or ctx['worked_example']
              or any(ctx['verdict_rubric'].values()) or ctx['source_links'])
    return ctx if filled else None


TEXT_KEYS = ('method', 'where_to_look', 'worked_example')


def _str_or_empty(value):
    return value.strip() if isinstance(value, str) else ''


def sanitize_ai_context(raw):
    """Keep only known ai_context keys with the right types (from untrusted imported data);
    None when nothing usable is left."""
    if not isinstance(raw, dict):
        return None
    ctx = {key: _str_or_empty(raw.get(key)) for key in TEXT_KEYS}
    rubric = raw.get('verdict_rubric') if isinstance(raw.get('verdict_rubric'), dict) else {}
    ctx['verdict_rubric'] = {key: _str_or_empty(rubric.get(key)) for key in RUBRIC_KEYS}
    links = raw.get('source_links') if isinstance(raw.get('source_links'), list) else []
    ctx['source_links'] = [link.strip() for link in links
                           if isinstance(link, str) and link.strip().startswith(('http://', 'https://'))]
    ctx['verdict_rubric'] = {key: value for key, value in ctx['verdict_rubric'].items() if value}
    cleaned = {key: value for key, value in ctx.items() if value}
    return cleaned or None


def ai_context_from_data(data):
    """ai_context for an item built from imported/template data: an explicit `ai_context` dict
    wins once sanitized (known keys, right types), else the legacy `llm_prompt` seeds the method."""
    return sanitize_ai_context(data.get('ai_context')) or ai_context_from_llm_prompt(data.get('llm_prompt'))


def ai_context_from_llm_prompt(text):
    """ai_context for an item that only has a legacy llm_prompt: the prompt becomes the method."""
    method = _clean(text)
    return {'method': method} if method else None


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
