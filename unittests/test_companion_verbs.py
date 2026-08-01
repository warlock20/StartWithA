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

"""Verb palette — the composer as a structured command.

A verb sets the stance; the user still names the subject. The stance text is sent
to the model, so it lives in YAML with the other prompts rather than in JS — and
can be reworded without touching code.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.argos.verbs import list_verbs

JS = os.path.join(os.path.dirname(__file__), '..', 'app/static/js/companion.js')
WIDGET = os.path.join(
    os.path.dirname(__file__), '..', 'app/templates/main/_companion_widget.html')
VERBS_YAML = os.path.join(
    os.path.dirname(__file__), '..',
    'app/services/ai/prompts/companion/verbs.yaml')
CSS = os.path.join(
    os.path.dirname(__file__), '..', 'app/static/css/modules/_companion.css')


def _js():
    return open(JS, encoding='utf-8').read()


def test_verbs_come_from_yaml_not_code():
    """Phrasing that reaches the model belongs in the prompt YAML."""
    assert os.path.exists(VERBS_YAML)
    js = _js()
    assert 'Red-team' not in js, 'verb labels must not be hardcoded in JS'


def test_every_verb_has_a_stance_and_a_placeholder():
    verbs = list_verbs()
    assert verbs, 'expected verbs to load'
    for verb in verbs:
        assert set(verb) >= {'key', 'label', 'icon', 'stance', 'placeholder'}
        assert verb['stance'].strip()
        assert verb['placeholder'].strip()


def test_the_four_supported_verbs_are_offered():
    """Each resolves to read-only tools the agent already has."""
    keys = {v['key'] for v in list_verbs()}
    assert {'compare', 'summarize', 'draft', 'redteam'} <= keys


def test_monitor_is_not_offered():
    """Every companion tool is read-only — nothing writes, schedules or watches.

    A Monitor verb would promise recurring attention the agent cannot deliver.
    Checkpoints are the real feature for that; they need a date and a metric.
    """
    keys = {v['key'] for v in list_verbs()}
    labels = ' '.join(v['label'] for v in list_verbs()).lower()
    assert 'monitor' not in keys
    assert 'monitor' not in labels


def test_verbs_do_not_carry_canned_questions():
    """A verb frames the request; it must not ship a library of guesses that rot."""
    for verb in list_verbs():
        assert 'suggestions' not in verb
        assert 'questions' not in verb


def test_slash_opens_the_palette():
    """Typing / in an empty composer is the keyboard route into the verbs."""
    s = _js()
    assert "'/'" in s
    assert 'companionVerbPalette' in s


def test_composer_grows_to_fit_the_stance():
    """The stance stays visible text, so the box has to make room for it.

    Keeping it editable is the point — the user should see what will be sent —
    which fails if it's clipped to one line.
    """
    s = _js()
    assert 'autoGrow' in s
    assert 'scrollHeight' in s

    css = open(CSS, encoding='utf-8').read()
    assert 'max-height: 72px' not in css, 'one-line ceiling clips a verb stance'


def test_actions_survive_the_verb_row():
    """Capture and Wrap Up are actions, not questions — verbs must not eat them."""
    s = _js()
    assert "action: 'capture'" in s
    assert "action: 'wrapup'" in s


def test_widget_renders_the_verb_row_from_the_server():
    html = open(WIDGET, encoding='utf-8').read()
    assert 'companionVerbPalette' in html
    assert 'companion_verbs()' in html
