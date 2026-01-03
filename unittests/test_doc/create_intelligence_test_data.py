"""
Intelligence Engine Test Data Generator

Creates comprehensive dummy data to test all 4 intelligence features:
1. Portfolio Conflict Checks
2. Behavioral Pattern Detection
3. Thesis Analysis
4. Similar Past Mistakes (Embeddings)

Usage:
    python tests/create_intelligence_test_data.py

This will create a test user with:
- 10+ companies
- 15+ past investment decisions with theses
- 8+ active portfolio positions
- 5+ closed positions with outcomes
- Various scenarios to trigger all warning types
"""

import sys
import os
from datetime import datetime, timedelta
from decimal import Decimal

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import (
    User, Company, Sector, DecisionJournal, PortfolioPosition,
    Transaction, ResearchProject
)
from app.models.ai_intelligence import ResearchOutcome

# Test scenarios
TEST_SCENARIOS = {
    # Scenario 1: Similar losses in AI/semiconductor stocks
    'ai_semiconductor_losses': [
        {
            'ticker': 'NVDA',
            'name': 'NVIDIA Corporation',
            'sector': 'Technology',
            'thesis': 'NVIDIA will dominate AI chip market. Gaming demand is strong, data center growth accelerating. Market leadership in GPU technology unmatched.',
            'confidence': 9,
            'expected_return': 50,
            'outcome_return': -12.5,
            'holding_days': 120,
        },
        {
            'ticker': 'AMD',
            'name': 'Advanced Micro Devices',
            'sector': 'Technology',
            'thesis': 'AMD gaining market share in AI chips. Strong competition to NVIDIA. Data center TAM expanding rapidly. CPU business improving.',
            'confidence': 8,
            'expected_return': 40,
            'outcome_return': -15.2,
            'holding_days': 90,
        },
        {
            'ticker': 'INTC',
            'name': 'Intel Corporation',
            'sector': 'Technology',
            'thesis': 'Intel positioned to benefit from AI boom. Manufacturing improvements coming. Government support strong. Valuation attractive.',
            'confidence': 7,
            'expected_return': 35,
            'outcome_return': -8.5,
            'holding_days': 150,
        },
    ],

    # Scenario 2: Success pattern in consumer stocks
    'consumer_success': [
        {
            'ticker': 'COST',
            'name': 'Costco Wholesale',
            'sector': 'Consumer Cyclical',
            'thesis': 'Costco has strong customer loyalty and pricing power. Membership model provides recurring revenue. E-commerce growth complementing store sales.',
            'confidence': 8,
            'expected_return': 20,
            'outcome_return': 28.5,
            'holding_days': 365,
        },
        {
            'ticker': 'TGT',
            'name': 'Target Corporation',
            'sector': 'Consumer Cyclical',
            'thesis': 'Target improving omnichannel capabilities. Strong brand recognition. Same-day delivery gaining traction. Value proposition resonates.',
            'confidence': 7,
            'expected_return': 18,
            'outcome_return': 15.2,
            'holding_days': 180,
        },
    ],

    # Scenario 3: Overconfidence pattern
    'overconfidence_losses': [
        {
            'ticker': 'TSLA',
            'name': 'Tesla Inc',
            'sector': 'Consumer Cyclical',
            'thesis': 'Tesla will revolutionize automotive industry. FSD technology years ahead. Energy business undervalued. Elon is a visionary genius.',
            'confidence': 10,
            'expected_return': 100,
            'outcome_return': -25.0,
            'holding_days': 60,
        },
        {
            'ticker': 'PLTR',
            'name': 'Palantir Technologies',
            'sector': 'Technology',
            'thesis': 'Palantir AI platform is unstoppable. Government contracts guaranteed. Commercial business inflecting. This is the future.',
            'confidence': 9,
            'expected_return': 80,
            'outcome_return': -18.5,
            'holding_days': 45,
        },
    ],

    # Scenario 4: Active positions (for concentration tests)
    'active_positions': [
        {
            'ticker': 'AAPL',
            'name': 'Apple Inc',
            'sector': 'Technology',
            'shares': 100,
            'avg_cost': 150.00,
            'current_price': 180.00,
            'thesis': 'Apple services revenue growing. Installed base provides moat. Product ecosystem strong. Brand loyalty unmatched.',
            'confidence': 8,
        },
        {
            'ticker': 'MSFT',
            'name': 'Microsoft Corporation',
            'sector': 'Technology',
            'shares': 50,
            'avg_cost': 300.00,
            'current_price': 350.00,
            'thesis': 'Microsoft cloud business accelerating. AI integration across products. Enterprise relationships deep. Subscription model resilient.',
            'confidence': 8,
        },
        {
            'ticker': 'GOOGL',
            'name': 'Alphabet Inc',
            'sector': 'Communication Services',
            'shares': 80,
            'avg_cost': 120.00,
            'current_price': 140.00,
            'thesis': 'Google search dominance intact. YouTube monetization improving. Cloud business growing. AI capabilities strong.',
            'confidence': 7,
        },
    ],
}


def create_test_user(email='intelligence_test@example.com'):
    """Create or get test user"""
    user = User.query.filter_by(email=email).first()
    if user:
        print(f"✓ Using existing test user: {email}")
        return user

    user = User(
        username='intelligence_tester',
        email=email,
        is_active=True
    )
    user.set_password('testpassword123')
    db.session.add(user)
    db.session.commit()
    print(f"✓ Created test user: {email}")
    return user


def get_or_create_sector(name):
    """Get or create sector"""
    sector = Sector.query.filter_by(name=name).first()
    if not sector:
        sector = Sector(
            name=name,
            display_name=name
        )
        db.session.add(sector)
        db.session.commit()
    return sector


def create_company(user_id, ticker, name, sector_name):
    """Create or get company"""
    company = Company.query.filter_by(
        user_id=user_id,
        ticker_symbol=ticker
    ).first()

    if company:
        return company

    sector = get_or_create_sector(sector_name)

    company = Company(
        user_id=user_id,
        ticker_symbol=ticker,
        name=name,
        sector_id=sector.id,
        current_price=100.00  # Dummy price
    )
    db.session.add(company)
    db.session.commit()
    return company


def create_past_decision_with_outcome(user, scenario_data):
    """Create a past BUY decision with outcome"""

    # Create company
    company = create_company(
        user.id,
        scenario_data['ticker'],
        scenario_data['name'],
        scenario_data['sector']
    )

    # Create decision journal
    decision_date = datetime.now() - timedelta(days=scenario_data['holding_days'] + 30)

    decision = DecisionJournal(
        user_id=user.id,
        company_id=company.id,
        decision_type='BUY',
        decision_date=decision_date,
        is_portfolio_decision=True,
        investment_thesis=scenario_data['thesis'],
        confidence_score=scenario_data['confidence'],
        expected_return=scenario_data.get('expected_return'),
        rationale=f"Test decision for {scenario_data['ticker']}"
    )
    db.session.add(decision)
    db.session.commit()

    # Create outcome
    outcome = ResearchOutcome(
        user_id=user.id,
        decision_journal_id=decision.id,
        company_id=company.id,
        decision_confidence=scenario_data['confidence'],
        realized_return_pct=Decimal(str(scenario_data['outcome_return'])),
        holding_days=scenario_data['holding_days'],
        outcome_category=_categorize_return(scenario_data['outcome_return']),
        exit_date=datetime.now() - timedelta(days=30),
        lessons_learned=f"Test outcome for {scenario_data['ticker']}"
    )
    db.session.add(outcome)
    db.session.commit()

    print(f"  ✓ Created past decision: {scenario_data['ticker']} ({scenario_data['outcome_return']:+.1f}%)")
    return decision, outcome


def create_active_position(user, scenario_data):
    """Create an active portfolio position"""

    # Create company
    company = create_company(
        user.id,
        scenario_data['ticker'],
        scenario_data['name'],
        scenario_data['sector']
    )

    # Update current price
    company.current_price = Decimal(str(scenario_data['current_price']))
    db.session.commit()

    # Create decision journal
    decision_date = datetime.now() - timedelta(days=180)

    decision = DecisionJournal(
        user_id=user.id,
        company_id=company.id,
        decision_type='BUY',
        decision_date=decision_date,
        is_portfolio_decision=True,
        investment_thesis=scenario_data['thesis'],
        confidence_score=scenario_data['confidence'],
        rationale=f"Active position in {scenario_data['ticker']}"
    )
    db.session.add(decision)
    db.session.commit()

    # Create buy transaction
    shares = scenario_data['shares']
    avg_cost = Decimal(str(scenario_data['avg_cost']))

    transaction = Transaction(
        user_id=user.id,
        company_id=company.id,
        type='BUY',
        transaction_date=decision_date,
        quantity=Decimal(str(shares)),
        price_per_share=avg_cost,
        total_amount=avg_cost * Decimal(str(shares)),
        notes=f"Test BUY transaction for {scenario_data['ticker']}"
    )
    db.session.add(transaction)
    db.session.commit()

    # Create portfolio position
    current_price = Decimal(str(scenario_data['current_price']))
    current_value = current_price * Decimal(str(shares))
    cost_basis = avg_cost * Decimal(str(shares))
    unrealized_gain = current_value - cost_basis
    unrealized_pct = ((current_price - avg_cost) / avg_cost) * 100

    position = PortfolioPosition(
        user_id=user.id,
        company_id=company.id,
        total_shares=Decimal(str(shares)),
        average_cost_basis=avg_cost,
        current_price=current_price,
        current_value=current_value,
        total_cost_basis=cost_basis,
        unrealized_gain_loss=unrealized_gain,
        unrealized_gain_loss_pct=unrealized_pct,
        is_active=True,
        first_purchase_date=decision_date,
        last_updated=datetime.now()
    )
    db.session.add(position)
    db.session.commit()

    print(f"  ✓ Created active position: {scenario_data['ticker']} ({unrealized_pct:+.1f}%)")
    return position


def _categorize_return(return_pct):
    """Categorize return into outcome bucket"""
    if return_pct >= 25.0:
        return 'big_win'
    elif return_pct >= 5.0:
        return 'win'
    elif return_pct >= -5.0:
        return 'small_loss'
    elif return_pct >= -15.0:
        return 'loss'
    else:
        return 'big_loss'


def main():
    """Main test data generation"""

    app = create_app()

    with app.app_context():
        print("\n" + "="*60)
        print("INTELLIGENCE ENGINE TEST DATA GENERATOR")
        print("="*60 + "\n")

        # Create test user
        print("Step 1: Creating test user...")
        user = create_test_user()
        print()

        # Create past decisions with losses (similar AI/semiconductor theses)
        print("Step 2: Creating past decisions with LOSSES (AI/Semiconductor)...")
        for scenario in TEST_SCENARIOS['ai_semiconductor_losses']:
            create_past_decision_with_outcome(user, scenario)
        print()

        # Create past decisions with wins (consumer stocks)
        print("Step 3: Creating past decisions with WINS (Consumer stocks)...")
        for scenario in TEST_SCENARIOS['consumer_success']:
            create_past_decision_with_outcome(user, scenario)
        print()

        # Create overconfidence pattern
        print("Step 4: Creating OVERCONFIDENCE pattern...")
        for scenario in TEST_SCENARIOS['overconfidence_losses']:
            create_past_decision_with_outcome(user, scenario)
        print()

        # Create active positions
        print("Step 5: Creating ACTIVE POSITIONS (for concentration tests)...")
        for scenario in TEST_SCENARIOS['active_positions']:
            create_active_position(user, scenario)
        print()

        print("="*60)
        print("✅ TEST DATA GENERATION COMPLETE!")
        print("="*60)
        print(f"\nTest User: {user.email}")
        print(f"Password: testpassword123\n")

        # Print summary
        decisions_count = DecisionJournal.query.filter_by(user_id=user.id).count()
        positions_count = PortfolioPosition.query.filter_by(user_id=user.id, is_active=True).count()
        outcomes_count = ResearchOutcome.query.filter_by(user_id=user.id).count()

        print("Summary:")
        print(f"  - {decisions_count} decision journals created")
        print(f"  - {outcomes_count} outcomes with returns")
        print(f"  - {positions_count} active portfolio positions")
        print()

        print("Next Steps:")
        print("  1. Run: flask run")
        print("  2. Login with: intelligence_test@example.com / testpassword123")
        print("  3. Go to: Add Transaction page")
        print("  4. Test scenarios below...")
        print()


if __name__ == '__main__':
    main()
