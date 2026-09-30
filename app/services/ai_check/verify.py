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

"""Checking that an extracted quote really appears in its source."""

import base64
import re

import fitz

_DASHES = dict.fromkeys(map(ord, '‒–—―−'), '-')
_QUOTES = {ord('“'): '"', ord('”'): '"', ord('‘'): "'", ord('’'): "'"}
_ELLIPSIS = re.compile(r'…|\.\.\.')


def normalize_text(text):
    text = (text or '').translate(_DASHES).translate(_QUOTES).lower()
    text = re.sub(r'(?<=\d),(?=\d{3})', '', text)  # 18,400 -> 18400
    text = text.replace('(', ' ').replace(')', ' ')
    return re.sub(r'\s+', ' ', text).strip()


def quote_in_texts(quote, texts):
    """True when every ellipsis-separated part of the quote appears in one of the texts."""
    parts = [normalize_text(p) for p in _ELLIPSIS.split(quote or '')]
    parts = [p for p in parts if p]
    if not parts:
        return False
    for text in texts:
        haystack = normalize_text(text)
        if all(part in haystack for part in parts):
            return True
    return False


def read_page_texts(path):
    if path.lower().endswith('.txt'):
        with open(path, encoding='utf-8', errors='replace') as handle:
            return [handle.read()]
    with fitz.open(path) as doc:
        return [page.get_text('text') for page in doc]


def _pdf_texts_from_b64(data):
    with fitz.open(stream=base64.b64decode(data), filetype='pdf') as doc:
        return [page.get_text('text') for page in doc]


def fetched_texts(responses):
    """Text of every successful web_fetch result in these API responses (as dicts)."""
    texts = []
    for message in responses:
        for block in message.get('content') or []:
            if block.get('type') != 'web_fetch_tool_result':
                continue
            result = block.get('content') or {}
            if result.get('type') != 'web_fetch_result':
                continue
            source = ((result.get('content') or {}).get('source')) or {}
            if source.get('type') == 'text':
                texts.append(source.get('data') or '')
            elif source.get('type') == 'base64' and source.get('media_type') == 'application/pdf':
                texts.extend(_pdf_texts_from_b64(source.get('data') or ''))
    return texts
