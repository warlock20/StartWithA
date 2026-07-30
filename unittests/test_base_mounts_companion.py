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
    assert 'companion-root' in html


def test_widget_hidden_for_anonymous(app_context, _app):
    with _app.test_request_context('/'):
        html = render_template('main/_companion_widget.html')  # no login_user
    assert 'companion-root' not in html


def test_companion_css_is_in_global_core_bundle():
    """The widget is global, so its CSS must live in css_core (not css_companies)."""
    src = open(os.path.join(os.path.dirname(__file__), '..', 'app/assets.py'),
               encoding='utf-8').read()
    core_section = src[src.index('css_core = Bundle('):src.index('css_companies = Bundle(')]
    assert "'css/modules/_companion.css'" in core_section
