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
Tests for the pluggable frontend analytics registry (``app/telemetry.py``).

No database or app context needed — ``get_active_provider`` is a pure function
of the config mapping.

The property that actually matters here is that the CSP origins travel with the
provider: app/__init__.py's policy allows only 'self' plus three CDNs for
scripts and 'self' for connect, so a provider whose origins don't reach the
header is silently blocked in the browser with no server-side error.
"""

import pytest

from app.telemetry import PROVIDERS, get_active_provider


def cfg(**overrides):
    """A config mapping with tracking enabled for Clarity unless overridden."""
    base = {'ANALYTICS_PROVIDER': 'clarity', 'ANALYTICS_SITE_ID': 'abc123'}
    base.update(overrides)
    return base


# ── Disabled by default ──────────────────────────────────────────────────────

def test_disabled_when_unconfigured():
    """The default deployment must serve no third-party script at all."""
    assert get_active_provider({}) is None


@pytest.mark.parametrize('bad', [
    {'ANALYTICS_PROVIDER': ''},
    {'ANALYTICS_PROVIDER': '   '},
    {'ANALYTICS_PROVIDER': 'clarrity', 'ANALYTICS_SITE_ID': 'abc123'},  # typo
    {'ANALYTICS_PROVIDER': 'clarity'},                                  # no id
    {'ANALYTICS_PROVIDER': 'clarity', 'ANALYTICS_SITE_ID': '  '},
])
def test_misconfiguration_fails_closed(bad):
    """A broken config disables tracking rather than raising or half-enabling."""
    assert get_active_provider(bad) is None


def test_site_id_with_markup_is_rejected():
    """Site ids reach a URL and an HTML attribute — reject anything exotic."""
    assert get_active_provider(cfg(ANALYTICS_SITE_ID='a"><script>x')) is None


def test_non_http_script_url_is_rejected():
    assert get_active_provider(cfg(ANALYTICS_SCRIPT_URL='javascript:alert(1)')) is None


# ── Enabled providers ────────────────────────────────────────────────────────

def test_clarity_builds_tag_url_and_requires_consent():
    p = get_active_provider(cfg())
    assert p['script_url'] == 'https://www.clarity.ms/tag/abc123'
    # Clarity sets _clck/_clsk and records sessions: opt-in before it loads.
    assert p['sets_cookies'] is True
    assert p['needs_consent'] is True


def test_consent_gate_can_be_disabled_explicitly():
    p = get_active_provider(cfg(ANALYTICS_REQUIRE_CONSENT=False))
    assert p['sets_cookies'] is True      # the provider hasn't changed
    assert p['needs_consent'] is False    # only the gate was waived


def test_clarity_declares_its_command_queue():
    """Clarity's own snippet defines window.clarity as a queue before the tag
    loads, so early clarity('identify', ...) calls survive. Dropping it makes
    any such call throw until the network request lands."""
    assert get_active_provider(cfg())['queue_global'] == 'clarity'


@pytest.mark.parametrize('key', ['plausible', 'umami'])
def test_script_tag_providers_declare_no_queue(key):
    """These install as a bare script tag + data attribute; inventing a global
    for them would shadow nothing and mislead."""
    p = get_active_provider({'ANALYTICS_PROVIDER': key,
                             'ANALYTICS_SITE_ID': 'example.com'})
    assert p['queue_global'] is None


def test_cookieless_provider_never_asks_for_consent():
    p = get_active_provider({'ANALYTICS_PROVIDER': 'plausible',
                             'ANALYTICS_SITE_ID': 'app.example.com'})
    assert p['sets_cookies'] is False
    assert p['needs_consent'] is False
    assert p['attrs'] == {'data-domain': 'app.example.com'}


# ── CSP origins ──────────────────────────────────────────────────────────────

def test_clarity_origins_reach_the_csp():
    """Without these the tag loads nowhere: script blocked, beacons blocked."""
    p = get_active_provider(cfg())
    assert 'https://www.clarity.ms' in p['script_src']
    assert 'https://*.clarity.ms' in p['connect_src']
    assert 'https://c.bing.com' in p['connect_src']


def test_clarity_allows_the_recorder_not_just_the_bootstrap():
    """Regression: script-src once listed only https://www.clarity.ms, the
    origin of the /tag/<id> URL. That bootstrap injects the real recorder from
    https://scripts.clarity.ms/<version>/clarity.js, so the narrow policy let
    the tag load and then blocked the script that does the actual recording —
    Clarity looked installed and captured nothing. Asserted as a wildcard
    because Microsoft owns the subdomain and version."""
    p = get_active_provider(cfg())
    assert 'https://*.clarity.ms' in p['script_src']


def test_self_hosted_url_replaces_vendor_origins():
    """A self-hoster talks only to their own box — don't widen the CSP to a CDN
    they deliberately opted out of."""
    p = get_active_provider({
        'ANALYTICS_PROVIDER': 'umami',
        'ANALYTICS_SITE_ID': 'a-uuid',
        'ANALYTICS_SCRIPT_URL': 'https://stats.example.com/script.js',
    })
    assert p['script_url'] == 'https://stats.example.com/script.js'
    assert p['script_src'] == ['https://stats.example.com']
    assert p['connect_src'] == ['https://stats.example.com']
    assert 'https://cloud.umami.is' not in p['script_src']


@pytest.mark.parametrize('key', sorted(PROVIDERS))
def test_every_provider_declares_usable_origins(key):
    """Guards new registry entries: a provider with no origins is unloadable."""
    p = get_active_provider({'ANALYTICS_PROVIDER': key,
                             'ANALYTICS_SITE_ID': 'example.com'})
    assert p is not None, f'{key} failed to resolve'
    assert p['script_src'], f'{key} declares no script-src origin'
    assert p['connect_src'], f'{key} declares no connect-src origin'
    assert p['script_url'].startswith('https://')
    # Every origin must be a bare scheme://host — a path here would be an
    # invalid CSP source and silently break the whole policy.
    for origin in p['script_src'] + p['connect_src']:
        assert origin.count('/') == 2, f'{key}: {origin!r} is not a bare origin'
