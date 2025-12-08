#!/usr/bin/env python3
"""Quick check of portfolio position state"""

from app import create_app, db
from app.models import PortfolioPosition, Transaction, Company

app = create_app()

with app.app_context():
    print("=" * 80)
    print("PORTFOLIO POSITION CHECK")
    print("=" * 80)
    print()

    # Check all positions
    all_positions = PortfolioPosition.query.all()
    print(f"Total positions in database: {len(all_positions)}")
    print()

    for pos in all_positions:
        print(f"Position ID: {pos.id}")
        print(f"  User ID: {pos.user_id}")
        print(f"  Company ID: {pos.company_id}")
        print(f"  Company: {pos.company.ticker_symbol} - {pos.company.name}")
        print(f"  Total Shares: {pos.total_shares}")
        print(f"  Is Active: {pos.is_active}")
        print(f"  Average Cost: ${pos.average_cost_basis}")
        print(f"  Current Price: ${pos.current_price if pos.current_price else 'N/A'}")
        print(f"  Last Price Update: {pos.last_price_update}")
        print()

    # Check active positions for user_id=1
    print("=" * 80)
    print("ACTIVE POSITIONS FOR USER_ID=1")
    print("=" * 80)
    print()

    active_positions = PortfolioPosition.query.filter_by(
        user_id=1,
        is_active=True
    ).all()

    print(f"Found {len(active_positions)} active positions for user_id=1")
    print()

    for pos in active_positions:
        print(f"  - {pos.company.ticker_symbol}: {pos.total_shares} shares")

    # Check transactions
    print()
    print("=" * 80)
    print("TRANSACTIONS FOR USER_ID=1")
    print("=" * 80)
    print()

    transactions = Transaction.query.filter_by(user_id=1).all()
    print(f"Found {len(transactions)} transactions for user_id=1")
    print()

    for txn in transactions:
        print(f"  - {txn.type} {txn.quantity} shares of {txn.company.ticker_symbol} on {txn.date}")

    print()
    print("=" * 80)
