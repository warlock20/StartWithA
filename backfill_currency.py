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
Currency Backfill Script

Fixes existing data for multi-currency support:
  A) Detect and set company.reporting_currency from ticker
  B) Populate _base fields on transactions where they're NULL
  C) Recalculate all portfolio positions with correct currency conversion

Usage:
    python backfill_currency.py           # Run all steps
    python backfill_currency.py companies # Only fix companies
    python backfill_currency.py transactions # Only fix transactions
    python backfill_currency.py positions # Only recalculate positions
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from app.models.company import Company
from app.models.portfolio import Transaction, PortfolioPosition, update_portfolio_position_for_company
from app.models.user import User
from app.services.currency_service import CurrencyService
from app.services.price_service import PriceService

app = create_app()


def backfill_company_currencies():
    """Step A: Detect and set reporting_currency for all companies."""
    print("\n=== Step A: Detecting company reporting currencies ===")

    companies = Company.query.filter(Company.reporting_currency.is_(None)).all()
    print(f"Found {len(companies)} companies without reporting_currency")

    updated = 0
    for company in companies:
        if not company.ticker_symbol:
            continue

        currency = CurrencyService.detect_currency_from_ticker(company.ticker_symbol)
        company.reporting_currency = currency
        updated += 1
        print(f"  {company.ticker_symbol} -> {currency}")

    db.session.commit()
    print(f"Updated {updated} companies")


def backfill_transaction_base_fields():
    """Step B: Populate _base fields on transactions where NULL."""
    print("\n=== Step B: Populating transaction _base fields ===")

    transactions = Transaction.query.filter(
        Transaction.price_per_share_base.is_(None),
        Transaction.type.in_(['BUY', 'SELL', 'DIVIDEND'])
    ).all()
    print(f"Found {len(transactions)} transactions without _base fields")

    # Group by user for efficiency
    user_cache = {}
    updated = 0
    errors = 0

    for txn in transactions:
        try:
            # Get user's base currency (cached)
            if txn.user_id not in user_cache:
                user = User.query.get(txn.user_id)
                user_cache[txn.user_id] = user.base_currency if user else 'USD'

            user_base = user_cache[txn.user_id]

            # The transaction currency should be the user's base currency
            # (since imported prices are in the user's currency)
            txn.currency = user_base

            # Calculate conversion (same currency = rate 1.0)
            from decimal import Decimal
            exchange_rate = CurrencyService.get_exchange_rate(
                from_currency=txn.currency,
                to_currency=user_base,
                rate_date=txn.date
            )

            txn.price_per_share_base = Decimal(str(txn.price_per_share)) * exchange_rate
            txn.fees_base = Decimal(str(txn.fees)) * exchange_rate
            txn.exchange_rate = exchange_rate
            txn.exchange_rate_date = txn.date

            updated += 1
            if updated % 50 == 0:
                print(f"  Processed {updated} transactions...")
                db.session.flush()

        except Exception as e:
            errors += 1
            print(f"  Error on txn {txn.id} ({txn.company_id}): {e}")

    db.session.commit()
    print(f"Updated {updated} transactions ({errors} errors)")


def recalculate_positions():
    """Step C: Recalculate all active positions with currency-aware FIFO."""
    print("\n=== Step C: Recalculating portfolio positions ===")

    positions = PortfolioPosition.query.filter_by(is_active=True).all()
    print(f"Found {len(positions)} active positions to recalculate")

    updated = 0
    errors = 0

    for position in positions:
        try:
            update_portfolio_position_for_company(
                company_id=position.company_id,
                user_id=position.user_id
            )
            updated += 1
            if updated % 10 == 0:
                print(f"  Recalculated {updated} positions...")
                db.session.flush()

        except Exception as e:
            errors += 1
            print(f"  Error on position {position.id} (company {position.company_id}): {e}")

    db.session.commit()
    print(f"Recalculated {updated} positions ({errors} errors)")


def main():
    step = sys.argv[1] if len(sys.argv) > 1 else 'all'

    with app.app_context():
        if step in ('all', 'companies'):
            backfill_company_currencies()

        if step in ('all', 'transactions'):
            backfill_transaction_base_fields()

        if step in ('all', 'positions'):
            recalculate_positions()

        print("\nDone!")


if __name__ == '__main__':
    main()
