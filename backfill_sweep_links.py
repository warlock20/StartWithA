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
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from app.models.market_sweep import CompanySweepLink, MarketSweepDecision
from app.services.sweep_link import backfill_decision_links

app = create_app()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true',
                        help='Report what would be created without committing')
    args = parser.parse_args()

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
