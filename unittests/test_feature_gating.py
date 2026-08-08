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
Tests for the FEATURE_GATING_ENABLED kill switch (``app/features.py``).

Progressive unlocking is off by default: every user sees every feature from
first login. The unlock tables and FeatureUnlockService are deliberately left
in place so the behaviour is one env var away from returning, which is exactly
why this needs a test — nothing else in the suite covered the gating path, so a
well-meaning cleanup could delete the short-circuit and silently re-lock the
product for every amateur user.

``user_has_feature`` is the single choke point: the require_feature decorator,
the has_feature() template helper, the sidebar and the inline checks in
research_workflow/utility_routes all resolve through it. Testing it therefore
covers every gate in the app.
"""

import pytest
from flask import Flask

from app.features import (
    FEATURE_TIERS,
    TIER_ACCESS,
    FEATURE_GROUPS,
    FEATURE_TO_GROUP,
    gating_enabled,
    user_has_feature,
)


class FakeUser:
    """The four attributes user_has_feature reads, defaulted to the most
    locked-down user possible: a brand new amateur with nothing unlocked."""

    def __init__(self, tier='amateur', show_advanced=False, unlocked=None):
        self.subscription_tier = tier
        self.show_advanced_features = show_advanced
        self.unlocked_features = unlocked or {}
        self.newly_unlocked_features = {}


def app_with(gating):
    app = Flask(__name__)
    app.config['FEATURE_GATING_ENABLED'] = gating
    return app


PRO_FEATURES = sorted(k for k, v in FEATURE_TIERS.items() if v == 'pro')


# ── Default: everything open ─────────────────────────────────────────────────

@pytest.mark.parametrize('feature', PRO_FEATURES)
def test_pro_features_are_open_to_a_new_amateur_when_gating_is_off(feature):
    """The whole point of the switch: a user with zero activity reaches every
    'pro' feature. Parametrised over the registry so a newly added pro feature
    is covered without editing this test."""
    with app_with(False).app_context():
        assert user_has_feature(FakeUser(), feature) is True


def test_unknown_feature_is_open():
    with app_with(False).app_context():
        assert user_has_feature(FakeUser(), 'feature_that_does_not_exist') is True


def test_gating_is_off_by_default_when_config_key_is_absent():
    """Absent key must read as off, not raise or fall through to gated."""
    app = Flask(__name__)          # no FEATURE_GATING_ENABLED set at all
    with app.app_context():
        assert gating_enabled() is False
        assert user_has_feature(FakeUser(), 'analytics') is True


def test_gating_is_off_outside_an_app_context():
    """gating_enabled() is called from a plain function that scripts and the
    CLI may invoke with no app pushed; it must not raise there."""
    assert gating_enabled() is False
    assert user_has_feature(FakeUser(), 'analytics') is True


# ── The switch genuinely restores the old behaviour ──────────────────────────

def test_setting_the_flag_relocks_pro_features_for_an_amateur():
    """Guards the escape hatch. If this fails the flag is decorative and the
    gated experience can no longer be restored."""
    with app_with(True).app_context():
        user = FakeUser()
        assert user_has_feature(user, 'analytics') is False
        assert user_has_feature(user, 'knowledge_hub') is False


def test_core_features_stay_open_when_gating_is_on():
    with app_with(True).app_context():
        user = FakeUser()
        for feature, tier in FEATURE_TIERS.items():
            if tier == 'core':
                assert user_has_feature(user, feature) is True, feature


@pytest.mark.parametrize('tier', sorted(t for t in TIER_ACCESS if t != 'amateur'))
def test_paid_tiers_keep_access_when_gating_is_on(tier):
    with app_with(True).app_context():
        assert user_has_feature(FakeUser(tier=tier), 'analytics') is True


def test_group_unlock_still_grants_its_features_when_gating_is_on():
    group = 'knowledge_learning'
    with app_with(True).app_context():
        user = FakeUser(unlocked={group: True})
        for feature in FEATURE_GROUPS[group]:
            assert user_has_feature(user, feature) is True, feature


def test_show_advanced_features_toggle_still_works_when_gating_is_on():
    with app_with(True).app_context():
        assert user_has_feature(FakeUser(show_advanced=True), 'analytics') is True


# ── Registry integrity ───────────────────────────────────────────────────────

def test_every_grouped_feature_is_a_known_feature():
    """A typo in FEATURE_GROUPS would create a group entry that never matches,
    leaving the feature permanently locked once gating is switched back on."""
    for feature, group in FEATURE_TO_GROUP.items():
        assert feature in FEATURE_TIERS, f'{feature!r} in group {group!r} is not a known feature'
