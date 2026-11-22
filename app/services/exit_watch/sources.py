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

"""Web sources for an exit-criteria check: resolve Gemini redirects, read publish dates of cited pages."""

import json
import logging
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from celery.exceptions import SoftTimeLimitExceeded

from app.services.ai_check import AICheckError
from app.services.ai_check.fetch import resolve_redirect
from app.utils.time_utils import add_days, date, now_utc, parse_date_string

LOG = logging.getLogger(__name__)
MAX_JSONLD_NODES = 500
GOOGLE_HOSTS = ('google.com', 'googleusercontent.com')
ISO_DATE = re.compile(r'(\d{4})-(\d{2})-(\d{2})')
RELATIVE_AGE = re.compile(r'^(\d+|an?)\s+(minute|hour|day|week|month|year)s?\s+ago$', re.IGNORECASE)
DAYS_PER_UNIT = {'minute': 0, 'hour': 0, 'day': 1, 'week': 7, 'month': 30, 'year': 365}
TEXT_DATE_FORMATS = ('%Y-%m-%d', '%B %d, %Y', '%b %d, %Y', '%B %d %Y', '%d %B %Y', '%d %b %Y')


@dataclass
class ResolvedSource:
    id: str
    url: str
    title: str
    published: Optional[date]
    date_source: Optional[str]
    page_date: Optional[date]
    search_date: Optional[str]
    fetched: bool = False  # its page was already requested (a redirect, or a cited source)


def _iso_date(value):
    match = ISO_DATE.match(value.strip()) if isinstance(value, str) else None
    if not match:
        return None
    try:
        return date(int(match[1]), int(match[2]), int(match[3]))
    except ValueError:
        return None


def _jsonld_dates(root):
    """datePublished values in a JSON-LD document (object, list or @graph), visiting a bounded number of nodes."""
    stack, visited = [root], 0
    while stack and visited < MAX_JSONLD_NODES:
        node = stack.pop()
        visited += 1
        if isinstance(node, list):
            stack.extend(reversed(node))
        elif isinstance(node, dict):
            stack.append(node.get('@graph'))
            if 'datePublished' in node:
                yield node['datePublished']


def page_published_date(html):
    """The page's own publish date from its metadata, or None."""
    soup = BeautifulSoup(html, 'html.parser')
    for attr in ('property', 'name'):
        tag = soup.find('meta', attrs={attr: 'article:published_time'})
        if tag and _iso_date(tag.get('content')):
            return _iso_date(tag.get('content'))
    for script in soup.find_all('script', attrs={'type': 'application/ld+json'}):
        try:
            data = json.loads(script.string or '')
        except (ValueError, RecursionError):
            continue
        for value in _jsonld_dates(data):
            if _iso_date(value):
                return _iso_date(value)
    tag = soup.find('time', attrs={'datetime': True})
    return _iso_date(tag['datetime']) if tag else None


def parse_text_date(text):
    """A date from free text: "2025-04-30", "April 30, 2025" or "3 days ago"; else None."""
    if not text or not isinstance(text, str):
        return None
    text = text.strip()
    for fmt in TEXT_DATE_FORMATS:
        parsed = parse_date_string(text, fmt)
        if parsed:
            return parsed.date()
    now = now_utc()
    if text.lower() == 'yesterday':
        return add_days(now, -1).date()
    match = RELATIVE_AGE.match(text)
    if match:
        amount = 1 if match[1].lower() in ('a', 'an') else int(match[1])
        return add_days(now, -(amount * DAYS_PER_UNIT[match[2].lower()])).date()
    return _iso_date(text)


def pick_date(search_date, page_date, model_date):
    """The best publish date and where it came from: search, then page, then the model's own."""
    for value, source in ((parse_text_date(search_date), 'search'), (page_date, 'page'),
                          (parse_text_date(model_date), 'model')):
        if value:
            return value, source
    return None, None


def _is_google(host):
    host = (host or '').lower()
    return any(host == h or host.endswith('.' + h) for h in GOOGLE_HOSTS)


def _real_page(url):
    """An http(s) URL on a host that isn't Google's: where a redirect may count as resolved."""
    parsed = urlparse(url or '')
    return parsed.scheme in ('http', 'https') and not _is_google(parsed.hostname)


def _page_date(status, body):
    return page_published_date(body) if status is not None and status < 400 and body else None


def _resolve_redirect(result, contact, client, resolver):
    """(url, page date) for a redirect result, or None when it never reached a real page.

    The redirect is followed now so the source can be listed; the body it lands on gives the page
    date for free. A chain that reached a real host and then timed out or ran past MAX_REDIRECTS
    keeps that last real hop, undated.
    """
    hops = []
    try:
        final_url, status, body = resolve_redirect(result.url, contact, client, resolver, hops=hops)
    except AICheckError as exc:
        real = [hop for hop in hops[1:] if _real_page(hop)]
        LOG.debug('Redirect %s failed after %s: %s', result.url, real[-1] if real else 'no real page', exc)
        return (real[-1], None) if real else None
    if not _real_page(final_url):
        LOG.debug('Redirect %s dropped (landed on %s)', result.url, final_url)
        return None
    return final_url, _page_date(status, body)


def resolve_sources(results, contact, client=None, resolver=None):
    """Resolve search results to real pages to list for the answer. Returns (sources, unresolved count).

    Only redirects are fetched here; other results keep their URL and search date, and their page
    dates are read once the answer cites them (add_page_dates). One bad source never aborts the
    batch: a redirect that fails is dropped.
    """
    sources, seen, unresolved = [], set(), 0
    for result in results:
        if result.is_redirect:
            try:
                resolved = _resolve_redirect(result, contact, client, resolver)
            except SoftTimeLimitExceeded:
                raise
            except Exception as exc:  # one hostile page must not abort the others
                LOG.warning('Source %s failed: %s', result.url, exc)
                resolved = None
        else:
            resolved = (result.url, None)
        if resolved is None:
            unresolved += 1
            continue
        url, page_date = resolved
        if url in seen:
            continue
        seen.add(url)
        published, date_source = pick_date(result.published, page_date, None)
        sources.append(ResolvedSource(f'S{len(sources) + 1}', url, result.title, published, date_source,
                                      page_date, result.published, fetched=result.is_redirect))
    return sources, unresolved


def add_page_dates(resolved, cited_ids, contact, client=None, resolver=None):
    """Read the page date of each cited source that has no search date and wasn't fetched yet.

    Updates the sources in place. A page that fails keeps its source, without a page date.
    """
    for source in resolved:
        if source.id not in cited_ids or source.fetched or parse_text_date(source.search_date):
            continue
        source.fetched = True
        try:
            _, status, body = resolve_redirect(source.url, contact, client, resolver)
            source.page_date = _page_date(status, body)
        except SoftTimeLimitExceeded:
            raise
        except AICheckError as exc:
            LOG.debug('Source %s not fetched: %s', source.url, exc)
        except Exception as exc:  # one hostile page must not abort the others
            LOG.warning('Source %s failed: %s', source.url, exc)
        source.published, source.date_source = pick_date(source.search_date, source.page_date, None)
