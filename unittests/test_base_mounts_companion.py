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

"""Companion widget is global: auth-gated, opt-out (seamless chat, #300)."""

import os

from flask import render_template
from flask_login import login_user

from app import db
from app.models.user import User

BASE = os.path.join(os.path.dirname(__file__), '..', 'app/templates/main/_base.html')
WIDGET = os.path.join(
    os.path.dirname(__file__), '..', 'app/templates/main/_companion_widget.html')


def test_base_includes_companion_widget():
    html = open(BASE, encoding='utf-8').read()
    assert '_companion_widget.html' in html


def test_rail_is_mounted_inside_the_app_layout():
    """State C docks the rail as a flex sibling of .app-main, so content shrinks.

    A floating widget could live anywhere in the document; a docked one cannot —
    it has to be inside .app-layout and after .app-main to take real estate.
    """
    html = open(BASE, encoding='utf-8').read()
    layout_at = html.find('class="app-layout"')
    main_at = html.find('class="app-main"')
    widget_at = html.find('_companion_widget.html')
    layout_end = html.find('{# /app-layout #}')
    assert -1 not in (layout_at, main_at, widget_at, layout_end)
    assert layout_at < main_at < widget_at < layout_end


def test_base_loads_markdown_libs_before_companion():
    """marked + DOMPurify are self-hosted and load before the companion widget."""
    html = open(BASE, encoding='utf-8').read()
    marked_at = html.find('vendor/marked.min.js')
    purify_at = html.find('vendor/purify.min.js')
    widget_at = html.find('_companion_widget.html')
    assert marked_at != -1 and purify_at != -1, 'markdown libs not loaded'
    assert marked_at < widget_at and purify_at < widget_at, 'libs must precede companion.js'


def test_widget_guard_is_auth_gated_opt_out():
    """Renders for authenticated users unless a page explicitly opts out."""
    html = open(WIDGET, encoding='utf-8').read()
    assert 'current_user.is_authenticated' in html
    assert 'companion_enabled | default(true)' in html
    assert 'data-focus-type' in html


def test_widget_renders_for_authenticated_user(app_context, _app):
    user = User(email='mount@example.com')
    db.session.add(user)
    db.session.commit()
    with _app.test_request_context('/'):
        login_user(user)
        html = render_template('main/_companion_widget.html')
    assert 'companionRail' in html


def test_widget_hidden_for_anonymous(app_context, _app):
    with _app.test_request_context('/'):
        html = render_template('main/_companion_widget.html')  # no login_user
    assert 'companionRail' not in html


def test_companion_css_is_in_global_core_bundle():
    """The widget is global, so its CSS must live in css_core (not css_companies)."""
    src = open(os.path.join(os.path.dirname(__file__), '..', 'app/assets.py'),
               encoding='utf-8').read()
    core_section = src[src.index('css_core = Bundle('):src.index('css_companies = Bundle(')]
    assert "'css/modules/_companion.css'" in core_section
