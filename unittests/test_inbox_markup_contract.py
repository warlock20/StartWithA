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

"""Static contract checks on the inbox template. No app or DB needed.

The Tabulator formatters build HTML by string concatenation, so every
interpolation of user-controlled text has to go through escapeHtml.
"""

import os

INBOX = os.path.join(
    os.path.dirname(__file__), '..', 'app/ideas/templates/inbox.html')


def _inbox():
    return open(INBOX, encoding='utf-8').read()


def test_escape_helper_is_defined():
    assert 'function escapeHtml(' in _inbox()


def test_escape_helper_covers_all_five_dangerous_characters():
    s = _inbox()
    for pattern in ('&amp;', '&lt;', '&gt;', '&quot;', '&#39;'):
        assert pattern in s, f'escapeHtml does not emit {pattern}'


def test_name_and_ticker_are_escaped():
    s = _inbox()
    assert 'escapeHtml(cell.getValue())' in s
    assert 'escapeHtml(row.ticker)' in s


def test_source_is_escaped():
    assert "'<span class=\"idea-source-cell\">' + escapeHtml(val)" in _inbox()


def test_idea_name_is_not_interpolated_into_an_inline_onclick():
    """A name containing a backslash or double quote used to break the button."""
    s = _inbox()
    assert 'onclick="openEvaluateModal(' not in s
    assert 'data-evaluate-id=' in s


def test_hover_card_script_is_loaded():
    assert "filename='js/thesis-hover-card.js'" in _inbox()


def test_hover_card_is_initialised_against_the_table():
    s = _inbox()
    assert 'initThesisHoverCard(' in s
    assert "container: '#inbox-table'" in s


def test_thesis_cell_carries_the_id_and_accessibility_hooks():
    s = _inbox()
    assert 'idea-thesis-cell has-detail' in s
    assert 'data-idea-id=' in s
    assert 'tabindex="0"' in s
    assert 'aria-expanded="false"' in s
    assert 'aria-controls="thesis-hover-card"' in s


def test_card_closes_when_tabulator_rebuilds_rows():
    """A sort or filter would otherwise strand the card over the wrong row."""
    s = _inbox()
    assert "'renderComplete'" in s
    assert 'thesisCard.close()' in s


def test_notes_are_searchable():
    assert 'data.notes.toLowerCase().indexOf(searchVal)' in _inbox()


def test_ideas_with_neither_thesis_nor_notes_are_inert():
    """No affordance when there is nothing to show."""
    assert 'const hasDetail = !!(val || row.notes);' in _inbox()


def test_thesis_formatter_escapes_all_user_text():
    """The thesis cell was the last unescaped XSS sink on this page.

    Both interpolations are user-controlled: the preview text is the idea's
    own thesis, and the aria-label carries the idea name. Dropping either
    escapeHtml call reopens the hole, so pin both.
    """
    s = _inbox()
    assert 'escapeHtml(preview)' in s
    assert 'aria-label="Show thesis and notes for \' + escapeHtml(row.name)' in s
