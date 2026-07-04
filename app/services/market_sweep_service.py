# Investment Checklist Platform
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
Market Sweep Service

Shared utilities for parsing CSV/Excel company files and seeding MarketSweep data.
Used by the Flask-Admin upload view and auto-seeded on app startup.
"""

import csv
import io
import logging
import os

import openpyxl

from app import db
from app.models.market_sweep import MarketSweep, MarketSweepCompany
from app.models.user import User

logger = logging.getLogger(__name__)

DEFAULT_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                                'data', 'market-sweeps')


def _norm_header(h):
    """Normalise header names: strip whitespace, lowercase, underscores."""
    if h is None:
        return ''
    return str(h).strip().lower().replace(' ', '_')


def parse_companies_file(file_or_path, filename=None):
    """Parse a CSV or Excel file and return a sorted list of company row dicts.

    Args:
        file_or_path: Either a file-like object (from Flask upload) or a
                      filesystem path string.
        filename:     Original filename (used to detect format). Required when
                      *file_or_path* is a file-like object. For path strings
                      the filename is derived automatically.

    Returns:
        List[dict] – rows sorted alphabetically by company_name, with
        normalised header keys.

    Raises:
        ValueError: If the file format is unsupported.
    """
    if filename is None:
        if isinstance(file_or_path, str):
            filename = file_or_path
        else:
            raise ValueError('filename is required when passing a file-like object')

    filename_lower = filename.lower()
    rows = []

    if filename_lower.endswith('.csv'):
        if isinstance(file_or_path, str):
            with open(file_or_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()
        else:
            content = file_or_path.read().decode('utf-8-sig')

        reader = csv.DictReader(io.StringIO(content))
        rows = [{_norm_header(k): v for k, v in r.items()} for r in reader]

    elif filename_lower.endswith(('.xlsx', '.xls')):
        if isinstance(file_or_path, str):
            wb = openpyxl.load_workbook(file_or_path)
        else:
            wb = openpyxl.load_workbook(file_or_path)

        ws = wb.active
        headers = [_norm_header(cell.value) for cell in ws[1]]
        for row in ws.iter_rows(min_row=2, values_only=True):
            if any(v is not None for v in row):
                rows.append(dict(zip(headers, row)))
    else:
        raise ValueError('Unsupported file format. Use CSV or Excel (.xlsx).')

    # Sort alphabetically by company_name
    rows.sort(key=lambda r: (r.get('company_name') or '').strip().lower())
    return rows


def seed_market_sweeps(data_dir=None):
    """Auto-seed MarketSweep records from CSV/Excel files on startup.

    Scans *data_dir* for .csv / .xlsx files.  Each filename is treated as
    the country name (e.g. ``Australia.csv`` → country "Australia").
    Sweeps that already exist in the database are silently skipped.

    Called once during app startup — safe to call repeatedly.
    """
    data_dir = data_dir or DEFAULT_DATA_DIR

    if not os.path.isdir(data_dir):
        return

    files = sorted(
        f for f in os.listdir(data_dir)
        if f.lower().endswith(('.csv', '.xlsx', '.xls'))
    )
    if not files:
        return

    admin_user = User.query.filter_by(is_admin=True).first()
    if not admin_user:
        logger.warning("seed_market_sweeps: no admin user found, skipping")
        return

    created = 0
    for filename in files:
        country = os.path.splitext(filename)[0]

        if MarketSweep.query.filter_by(country=country).first():
            continue

        filepath = os.path.join(data_dir, filename)
        try:
            rows = parse_companies_file(filepath)
        except Exception as e:
            logger.error("seed_market_sweeps: error parsing %s — %s", filename, e)
            continue

        sweep = MarketSweep(
            name=f"{country} Market Sweep",
            country=country,
            description=f"Auto-seeded from {filename}",
            uploaded_by=admin_user.id,
        )
        db.session.add(sweep)
        db.session.flush()

        count = 0
        for idx, row in enumerate(rows):
            name = str(row.get('company_name') or '').strip()
            if not name:
                continue
            company = MarketSweepCompany(
                sweep_id=sweep.id,
                company_name=name,
                ticker=str(row.get('ticker') or '').strip() or None,
                sector_label=str(row.get('sector') or '').strip() or None,
                market_cap=str(row.get('market_cap') or '').strip() or None,
                exchange=str(row.get('exchange') or '').strip() or None,
                sort_order=idx,
            )
            db.session.add(company)
            count += 1

        sweep.total_companies = count
        db.session.commit()
        created += 1
        logger.info("seed_market_sweeps: created %s — %d companies", country, count)

    if created:
        logger.info("seed_market_sweeps: seeded %d new sweep(s)", created)
