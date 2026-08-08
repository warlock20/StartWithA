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
Pluggable frontend analytics — off unless a self-hoster opts in.

Named ``telemetry`` rather than ``analytics`` because ``app/analytics/`` is
already the blueprint for user-facing *research* analytics, which is a wholly
different thing from third-party page tracking.

With ``ANALYTICS_PROVIDER`` unset (the default) nothing here does anything: no
third-party script is served, the CSP is unchanged, and the cookie notice's
"no tracking cookies are used" claim stays true. An operator turns tracking on
with two environment variables and no code or template edits.

Each provider declares:
  * the origins it needs, so the CSP is widened ONLY for the enabled one —
    without this the tag is silently blocked by app/__init__.py's policy;
  * whether it sets cookies, so cookie-based providers can be gated behind
    explicit opt-in (TDDDG § 25(1) / GDPR Art. 6(1)(a)) while cookieless ones
    load straight away.

Adding a provider is a dict entry — no changes to the CSP code or templates.
"""

import logging
import re
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

# ``{site_id}`` is substituted into ``script`` for the built-in URLs only; an
# operator-supplied ANALYTICS_SCRIPT_URL is used verbatim (never .format()ted,
# so a stray brace in config can't reach str.format's attribute access).
#
# ``queue_global`` names a global that must exist as a command queue BEFORE the
# vendor script arrives, so calls made during page load are replayed once it
# does. Vendors whose install is just "script tag + data attribute" leave it
# None. (PostHog is deliberately absent: its install requires a posthog.init()
# call, not a data attribute, so a registry entry of this shape would look
# configured and silently collect nothing. Add it with a real init hook.)
PROVIDERS = {
    'clarity': {
        'label': 'Microsoft Clarity',
        'script': 'https://www.clarity.ms/tag/{site_id}',
        'attrs': {},
        'queue_global': 'clarity',
        # The /tag/<id> URL is only a bootstrap: it injects a SECOND script,
        # currently https://scripts.clarity.ms/<version>/clarity.js, which is
        # what actually records. Allowing only the tag's own origin loads the
        # bootstrap and then blocks the recorder — Clarity appears installed
        # and collects nothing. The subdomain and version are Microsoft's to
        # change, so match the whole zone rather than pinning one host.
        'script_src': ['https://*.clarity.ms'],
        # Uploads go to b.clarity.ms/collect; c.bing.com covers the Bing UET
        # cookies (_uetmsclkid/_uetvid) the tag declares.
        'connect_src': ['https://*.clarity.ms', 'https://c.bing.com'],
        'sets_cookies': True,   # _clck / _clsk, plus session replay
    },
    'plausible': {
        'label': 'Plausible',
        'script': 'https://plausible.io/js/script.js',
        'attrs': {'data-domain': '{site_id}'},
        'queue_global': None,
        'script_src': ['https://plausible.io'],
        'connect_src': ['https://plausible.io'],
        'sets_cookies': False,
    },
    'umami': {
        'label': 'Umami',
        'script': 'https://cloud.umami.is/script.js',
        'attrs': {'data-website-id': '{site_id}'},
        'queue_global': None,
        'script_src': ['https://cloud.umami.is'],
        'connect_src': ['https://cloud.umami.is'],
        'sets_cookies': False,
    },
}

# Site ids land in a URL and in HTML attributes. Operator-supplied config is
# trusted, but the charset is narrow anyway (Clarity ids are alphanumeric,
# Plausible takes a domain, Umami a UUID) so rejecting anything else is free.
_SITE_ID_RE = re.compile(r'[A-Za-z0-9_.\-]{1,64}')


def _origin(url):
    """``https://host:port`` for a URL, or None if it isn't absolute http(s)."""
    parts = urlsplit(url)
    if parts.scheme not in ('http', 'https') or not parts.netloc:
        return None
    return f'{parts.scheme}://{parts.netloc}'


def get_active_provider(config):
    """
    Resolve the configured analytics provider, or None when tracking is off.

    Returns None — quietly for the default case, with a warning for a broken
    one — rather than raising: a typo in an env var should not take the site
    down, and half-configured tracking should fail closed.
    """
    key = (config.get('ANALYTICS_PROVIDER') or '').strip().lower()
    if not key:
        return None

    spec = PROVIDERS.get(key)
    if spec is None:
        logger.warning(
            "ANALYTICS_PROVIDER=%r is not a known provider (%s) — analytics disabled",
            key, ', '.join(sorted(PROVIDERS)))
        return None

    site_id = (config.get('ANALYTICS_SITE_ID') or '').strip()
    if not site_id:
        logger.warning(
            "ANALYTICS_PROVIDER=%s set but ANALYTICS_SITE_ID is empty — analytics disabled", key)
        return None
    if not _SITE_ID_RE.fullmatch(site_id):
        logger.warning(
            "ANALYTICS_SITE_ID contains unexpected characters — analytics disabled")
        return None

    override = (config.get('ANALYTICS_SCRIPT_URL') or '').strip()
    script_url = override or spec['script'].format(site_id=site_id)

    origin = _origin(script_url)
    if origin is None:
        logger.warning(
            "ANALYTICS_SCRIPT_URL=%r is not an absolute http(s) URL — analytics disabled",
            script_url)
        return None

    # A self-hosted deployment talks only to its own origin, so an override
    # REPLACES the vendor origins rather than adding to them — no point
    # widening the CSP to a CDN the operator has deliberately opted out of.
    script_src = [origin] if override else sorted({origin, *spec['script_src']})
    connect_src = [origin] if override else sorted({origin, *spec['connect_src']})

    return {
        'key': key,
        'label': spec['label'],
        'script_url': script_url,
        'attrs': {name: tpl.format(site_id=site_id)
                  for name, tpl in spec['attrs'].items()},
        'queue_global': spec.get('queue_global'),
        'sets_cookies': spec['sets_cookies'],
        'needs_consent': bool(
            spec['sets_cookies'] and config.get('ANALYTICS_REQUIRE_CONSENT', True)),
        'script_src': script_src,
        'connect_src': connect_src,
    }
