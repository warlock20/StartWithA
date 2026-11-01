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
Split one knowledge item's text into pieces for the companion's search index.

Pieces are about TARGET_WORDS long, break at sentence ends, prefer paragraph
ends, and start with the last sentence or two of the piece before (overlap), so
a fact near a break is still found with its lead-in. Short text stays whole.

Paragraphs are lines: the indexer flattens BlockNote notes one block per line.
Pure function: no DB, no AI.
"""

import re

TARGET_WORDS = 200
MAX_OVERLAP_SENTENCES = 2
MAX_OVERLAP_WORDS = 50

_SENTENCE_END = re.compile(r'(?<=[.!?])\s+')


def split(text):
    """Split text into pieces of at most TARGET_WORDS words (overlap included)."""
    text = (text or '').strip()
    if not text:
        return []
    if _count(text) <= TARGET_WORDS:
        return [text]

    paragraphs = [_sentences(line) for line in text.splitlines() if line.strip()]
    pieces = []
    current = []  # (paragraph index, sentence)

    for p_index, sentences in enumerate(paragraphs):
        used = _units_words(current)
        para_words = sum(_count(s) for s in sentences)
        # End the piece at this paragraph break rather than mid-paragraph,
        # unless that would leave it short.
        if current and used >= TARGET_WORDS // 2 and used + para_words > TARGET_WORDS:
            pieces.append(_join(current))
            current = _overlap(current, TARGET_WORDS - _count(sentences[0]))

        for sentence in sentences:
            words = _count(sentence)
            if current and _units_words(current) + words > TARGET_WORDS:
                pieces.append(_join(current))
                current = _overlap(current, TARGET_WORDS - words)
            current.append((p_index, sentence))

    if current:
        pieces.append(_join(current))
    return pieces


def _sentences(paragraph):
    """A paragraph's sentences; one longer than TARGET_WORDS is cut into word windows."""
    out = []
    for sentence in _SENTENCE_END.split(paragraph.strip()):
        words = sentence.split()
        for start in range(0, len(words), TARGET_WORDS):
            out.append(' '.join(words[start:start + TARGET_WORDS]))
    return [s for s in out if s]


def _overlap(units, room):
    """The trailing sentences to repeat at the start of the next piece."""
    budget = min(MAX_OVERLAP_WORDS, room)
    carried = []
    for unit in reversed(units[-MAX_OVERLAP_SENTENCES:]):
        if _units_words(carried) + _count(unit[1]) > budget:
            break
        carried.insert(0, unit)
    return carried


def _join(units):
    """Sentences of one paragraph joined by spaces, paragraphs by newlines."""
    lines = []
    last_paragraph = None
    for p_index, sentence in units:
        if p_index == last_paragraph:
            lines[-1] += ' ' + sentence
        else:
            lines.append(sentence)
            last_paragraph = p_index
    return '\n'.join(lines)


def _units_words(units):
    return sum(_count(sentence) for _, sentence in units)


def _count(text):
    return len(text.split())
