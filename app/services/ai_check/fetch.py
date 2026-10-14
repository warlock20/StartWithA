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

"""Downloading a web source for the AI check: SSRF-guarded, size-capped, cached per run."""

import ipaddress
import os
import shutil
import socket
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.services.ai_check import AICheckError

MAX_FETCH_BYTES = 22 * 1024 * 1024  # same cap as an uploaded document
# About 400k tokens: a larger text would not fit the context window of the models we use.
MAX_TEXT_CHARS = 1_500_000
MAX_REDIRECTS = 5
TIMEOUT_SECONDS = 30
# Filings often put these in cells of their own; they belong to the neighbouring number.
OPENING_CELLS = {'(', '$', '€', '£', '¥', '₸', '-(', '($'}
CLOSING_CELLS = {')', '%', ')%', '%)'}
BLOCK_TAGS = ['p', 'div', 'br', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'section', 'article',
              'header', 'footer', 'table', 'pre', 'blockquote', 'dt', 'dd']


def run_files_dir(upload_folder, run_id):
    return os.path.join(upload_folder, 'ai_check', str(run_id))


def _cached_file(upload_folder, run_id, source_id):
    for ext in ('pdf', 'txt'):
        path = os.path.join(run_files_dir(upload_folder, run_id), f'{source_id}.{ext}')
        if os.path.exists(path):
            return path
    return None


def _resolve(host):
    return {info[4][0] for info in socket.getaddrinfo(host, None)}


def check_public_host(host, resolver=_resolve):
    """Refuse hosts that resolve to private, loopback, link-local, reserved or multicast addresses.
    URLs come from model output, so this is the SSRF guard."""
    try:
        addresses = resolver(host)
    except OSError:
        raise AICheckError(f'Could not resolve {host}.')
    for address in addresses:
        ip = ipaddress.ip_address(address.split('%')[0])
        if not ip.is_global or ip.is_multicast:
            raise AICheckError(f'{host} points to a private or reserved address.')


def download(url, contact, client=None, resolver=_resolve):
    """GET `url`, following at most MAX_REDIRECTS redirects and re-checking every hop.
    Returns (content type, body). Every failure is an AICheckError (the source fails, no retry)."""
    if not contact:
        raise AICheckError('Web fetching is not configured on the server.')
    headers = {'User-Agent': f'StartWithA AI check ({contact})'}
    own_client = client is None
    client = client or httpx.Client(timeout=TIMEOUT_SECONDS, follow_redirects=False)
    try:
        for _ in range(MAX_REDIRECTS + 1):
            parsed = urlparse(url)
            if parsed.scheme not in ('http', 'https') or not parsed.hostname:
                raise AICheckError(f'Not a web address: {url}')
            check_public_host(parsed.hostname, resolver)
            with client.stream('GET', url, headers=headers) as response:
                if response.is_redirect:
                    url = urljoin(url, response.headers.get('location', ''))
                    continue
                if response.status_code >= 400:
                    raise AICheckError(f'The page returned HTTP {response.status_code}.')
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_FETCH_BYTES:
                        raise AICheckError('The page is larger than 22 MB.')
                return response.headers.get('content-type', ''), bytes(body)
        raise AICheckError('Too many redirects.')
    except httpx.TimeoutException:
        raise AICheckError('The page took too long to respond.')
    except httpx.HTTPError as exc:
        raise AICheckError(f'Could not download the page: {exc}')
    finally:
        if own_client:
            client.close()


def html_to_text(markup):
    """Readable text: one line per block element and per table row, cells joined by ' | '."""
    soup = BeautifulSoup(markup, 'html.parser')
    for tag in soup(['script', 'style', 'noscript', 'template']):
        tag.decompose()
    for row in soup.find_all('tr'):
        cells = [' '.join(cell.get_text(' ', strip=True).split()) for cell in row.find_all(['td', 'th'])]
        row.replace_with('\n' + ' | '.join(_merge_punctuation_cells(cell for cell in cells if cell)) + '\n')
    for tag in soup.find_all(BLOCK_TAGS):
        tag.insert_after('\n')
    lines = (' '.join(line.split()) for line in soup.get_text().splitlines())
    return '\n'.join(line for line in lines if line)


def _merge_punctuation_cells(cells):
    """Join "(", "$", ")", "%" cells onto their number: ['(', '11,663', ')'] -> ['(11,663)']."""
    merged, pending = [], ''
    for cell in cells:
        if cell in OPENING_CELLS:
            pending += cell
        elif cell in CLOSING_CELLS and merged and not pending:
            merged[-1] += cell
        else:
            merged.append(pending + cell)
            pending = ''
    if pending:
        merged.append(pending)
    return merged


def _kind(content_type, body):
    media = content_type.split(';')[0].strip().lower()
    if media == 'application/pdf' or body[:5] == b'%PDF-':
        return 'pdf'
    if media in ('text/html', 'application/xhtml+xml') or (not media and b'<html' in body[:1024].lower()):
        return 'html'
    if media.startswith('text/'):
        return 'text'
    raise AICheckError(f'Unsupported content type: {media or "unknown"}.')


def fetch_source_file(source, upload_folder, contact):
    """The local file for a web source: the cached copy, or a fresh download saved as .pdf or .txt.
    Returns (path, downloaded)."""
    cached = _cached_file(upload_folder, source.run_id, source.id)
    if cached:
        return cached, False
    content_type, body = download(source.url, contact)
    kind = _kind(content_type, body)
    folder = run_files_dir(upload_folder, source.run_id)
    if kind == 'pdf':
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f'{source.id}.pdf')
        with open(path, 'wb') as handle:
            handle.write(body)
        return path, True
    text = html_to_text(body) if kind == 'html' else body.decode('utf-8', errors='replace')
    if len(text) > MAX_TEXT_CHARS:
        raise AICheckError('The page is too long to read in one request.')
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f'{source.id}.txt')
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write(text)
    return path, True


def clear_run_files(upload_folder, run_id):
    shutil.rmtree(run_files_dir(upload_folder, run_id), ignore_errors=True)


def sweep_run_files(upload_folder, keep):
    """Delete every run folder whose run id `keep` rejects. Returns how many were removed."""
    root = os.path.join(upload_folder, 'ai_check')
    if not os.path.isdir(root):
        return 0
    removed = 0
    for name in os.listdir(root):
        if name.isdigit() and not keep(int(name)):
            clear_run_files(upload_folder, int(name))
            removed += 1
    return removed
