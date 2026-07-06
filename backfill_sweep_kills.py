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
Backfill Start-with-A's kills into the Idea Pipeline / Too-Hard Basket.

Historically, killing a company in the Start-with-A's market-sweep flow only
wrote a MarketSweepDecision row. The Too-Hard Basket service reads from
IdeaPipeline / ResearchProject, so those legacy kills were invisible.

This script finds every MarketSweepDecision with decision='killed' and
promoted_idea_id IS NULL, creates a matching IdeaPipeline row with
status='killed', and links the decision to the new idea.

Usage:
    python backfill_sweep_kills.py           # Run the backfill (idempotent — only touches orphans)
    python backfill_sweep_kills.py --dry-run # Show what would happen without committing
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import func

from app import create_app, db
from app.models import (
    Company,
    IdeaPipeline,
    MarketSweepCompany,
    MarketSweepDecision,
    Sector,
)
from app.services.sector_service import SectorService
from app.utils.time_utils import now_utc

app = create_app()

BATCH_SIZE = 100


def resolve_or_create_company(sweep_company, user_id, sector_id=None):
    """Mirror the helper in sweep_routes._resolve_or_create_company for a given user_id."""
    existing = None
    if sweep_company.ticker:
        existing = Company.query.filter(
            Company.user_id == user_id,
            Company.ticker_symbol == sweep_company.ticker,
        ).first()
    if not existing:
        existing = Company.query.filter(
            Company.user_id == user_id,
            func.lower(Company.name) == sweep_company.company_name.lower(),
        ).first()

    if existing:
        return existing.id

    sector_obj = None
    if sector_id:
        sector_obj = Sector.query.get(sector_id)
    elif sweep_company.sector_label:
        sector_obj = SectorService.find_or_create_sector(
            user_id=user_id,
            sector_name=sweep_company.sector_label,
            auto_create=True,
        )

    new_company = Company(
        user_id=user_id,
        name=sweep_company.company_name,
        ticker_symbol=sweep_company.ticker or 'UNKNOWN',
        sector_id=sector_obj.id if sector_obj else None,
    )
    db.session.add(new_company)
    db.session.flush()
    return new_company.id


def reconstruct_kill_reason(decision):
    """Build a kill_reason text from legacy MarketSweepDecision data."""
    reasons = decision.kill_reasons
    if isinstance(reasons, list) and reasons:
        # Easy-kill structured marker
        if isinstance(reasons[0], dict) and reasons[0].get('mode') == 'easy':
            return reasons[0].get('reason') or 'Legacy easy kill'
        # Checklist results
        failed = [r for r in reasons if isinstance(r, dict) and r.get('result') == 'fail']
        total = len(reasons)
        if failed:
            questions = [r.get('question', '') for r in failed if r.get('question')]
            summary = f'Failed {len(failed)} of {total} criteria'
            if questions:
                summary += ': ' + '; '.join(questions)
            return summary
        return f'Checklist kill ({total} criteria evaluated)'
    if decision.notes:
        return decision.notes
    return 'Legacy market-sweep kill'


def backfill(dry_run=False):
    orphans = MarketSweepDecision.query.filter(
        MarketSweepDecision.decision == 'killed',
        MarketSweepDecision.promoted_idea_id.is_(None),
    ).all()

    total = len(orphans)
    print(f'\n=== Backfilling Start-with-A kills → IdeaPipeline ===')
    print(f'Found {total} orphaned killed decisions')
    if dry_run:
        print('(dry-run: no changes will be committed)')

    if total == 0:
        print('Nothing to do.')
        return

    backfilled = 0
    skipped = 0
    errors = 0

    for idx, decision in enumerate(orphans, 1):
        try:
            sweep_company = MarketSweepCompany.query.get(decision.sweep_company_id)
            if not sweep_company:
                skipped += 1
                print(f'  [{idx}/{total}] SKIP — sweep_company {decision.sweep_company_id} missing')
                continue

            decided_at = decision.decided_at or now_utc()
            kill_reason = reconstruct_kill_reason(decision)

            if dry_run:
                print(f'  [{idx}/{total}] WOULD BACKFILL user={decision.user_id} '
                      f'company="{sweep_company.company_name}" reason="{kill_reason[:60]}..."')
                backfilled += 1
                continue

            company_id = resolve_or_create_company(
                sweep_company,
                user_id=decision.user_id,
                sector_id=decision.sector_id,
            )

            idea = IdeaPipeline(
                user_id=decision.user_id,
                name=sweep_company.company_name,
                idea_type='company',
                ticker_symbol=sweep_company.ticker,
                company_id=company_id,
                sector_id=decision.sector_id,
                source='market_sweep',
                status='killed',
                kill_reason=kill_reason,
                killed_at=decided_at,
                created_at=decided_at,
            )
            db.session.add(idea)
            db.session.flush()

            decision.promoted_idea_id = idea.id
            backfilled += 1

            if backfilled % BATCH_SIZE == 0:
                db.session.commit()
                print(f'  [{idx}/{total}] Committed batch — {backfilled} backfilled so far')

        except Exception as e:
            errors += 1
            db.session.rollback()
            print(f'  [{idx}/{total}] ERROR on decision {decision.id}: {e}')

    if not dry_run:
        db.session.commit()

    print(f'\nDone. Backfilled: {backfilled}, Skipped: {skipped}, Errors: {errors}')


def main():
    dry_run = '--dry-run' in sys.argv

    with app.app_context():
        backfill(dry_run=dry_run)


if __name__ == '__main__':
    main()
