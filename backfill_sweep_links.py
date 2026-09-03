#!/usr/bin/env python3
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
Backfill the company link behind every existing market-sweep decision.

Deciding on a sweep row already states which company it is. Before step 2 of
issue #330 that statement was implicit in the decision's idea; this makes it a
stored link.

Creates nothing where a decision carries no idea, or its idea no company, and
never overwrites a link that already exists.

Usage:
    python backfill_sweep_links.py           # run it
    python backfill_sweep_links.py --dry-run # report without committing
    python backfill_sweep_links.py --env RAILWAY_DB_PUBLIC_URL

WARNING: this builds the Flask app, whose startup seeds market sweeps from the
files on THIS machine's disk — unconditionally, for any database it is pointed
at. Targeting a remote database from a workstation therefore applies that
workstation's data to it. Prefer running the script inside the target's own
environment. (Demo-mode seeding is disabled for a targeted run; see
TargetConfig.)
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from app.models.market_sweep import CompanySweepLink, MarketSweepDecision
from app.services.sweep_link import backfill_decision_links
from config import Config


def resolve_database_url(env_var, url):
    """The database this run should target, or None to use the default.

    Mirrors scripts/dedupe_companies.py: an explicit --url wins, otherwise the
    named environment variable is read. config.py already loads .env at import
    time (before this ever runs), so the named var is visible without reloading it.

    The legacy ``postgres://`` scheme is rewritten the way Config does it —
    SQLAlchemy has no dialect under that name, and hosted Postgres still hands
    out URLs in that form.
    """
    resolved = url or os.environ.get(env_var)
    if resolved and resolved.startswith('postgres://'):
        return resolved.replace('postgres://', 'postgresql://', 1)
    return resolved


def build_target_config(target):
    """A Config pointed at *target* — nothing else about the app changes.

    DEMO_MODE is forced off. Inheriting this workstation's value would let app
    startup create schema and a demo user in the TARGETED database: naming a
    URL says where to read links from, not that the target should be turned
    into a demo environment.
    """
    class TargetConfig(Config):
        SQLALCHEMY_DATABASE_URI = target
        DEMO_MODE = False

    return TargetConfig


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true',
                        help='Report what would be created without committing')
    parser.add_argument('--env', default='DATABASE_URL',
                        help='environment variable holding the connection URL')
    parser.add_argument('--url', help='connection URL (overrides --env)')
    args = parser.parse_args()

    target = resolve_database_url(args.env, args.url)
    if target:
        app = create_app(build_target_config(target))
    else:
        app = create_app()

    with app.app_context():
        decisions = MarketSweepDecision.query.count()
        before = CompanySweepLink.query.count()
        created = backfill_decision_links()

        if args.dry_run:
            db.session.rollback()
            print(f'Dry run: {decisions} decision(s) -> {created} new link(s). '
                  f'Nothing committed.')
            return

        db.session.commit()
        after = CompanySweepLink.query.count()
        print(f'{decisions} decision(s) -> {created} new link(s). '
              f'Links: {before} -> {after}.')


if __name__ == '__main__':
    main()
