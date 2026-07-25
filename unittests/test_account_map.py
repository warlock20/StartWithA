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

"""Account map builder — cheap DB skeleton for the agent (Task 9). DB-backed."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.argos.account_map import build_account_map, render_account_map


def test_account_map_shape_and_holdings(app_context, seed_portfolio):
    uid = seed_portfolio
    amap = build_account_map(uid, focus={'type': 'portfolio'})

    assert amap['focus']['type'] == 'portfolio'
    assert 'holdings' in amap and 'counts' in amap
    assert amap['counts']['holdings'] == len(amap['holdings']) >= 1

    holding = amap['holdings'][0]
    assert {'company_id', 'name', 'ticker', 'weight_pct'} <= set(holding)


def test_render_account_map_is_nonempty_text(app_context, seed_portfolio):
    text = render_account_map(build_account_map(seed_portfolio))
    assert isinstance(text, str) and text.strip()


def test_account_map_scoped_to_user(app_context, seed_portfolio, other_user):
    assert build_account_map(other_user)['holdings'] == []


def test_account_map_surfaces_journal_and_mistakes(app_context, seed_portfolio_with_history):
    uid, cid = seed_portfolio_with_history
    amap = build_account_map(uid)

    assert amap['counts']['journal_entries'] >= 1
    assert amap['counts']['mistakes'] >= 1

    holding = next(h for h in amap['holdings'] if h['company_id'] == cid)
    assert holding['notes'] >= 1
    assert holding['mistakes'] >= 1

    # The rendered skeleton must advertise the mistake history to the agent.
    text = render_account_map(amap)
    assert 'mistake' in text.lower()
