#!/usr/bin/env python3
"""
Test script for AI Outcome Tracking System

Tests the complete flow:
1. BUY transaction → Create ResearchOutcome
2. SELL transaction → Update ResearchOutcome
3. Correlation analysis triggers
4. AIInsight generation

Usage:
    python test_outcome_tracking.py
"""

import sys
import os
from datetime import datetime, date, timedelta
from decimal import Decimal

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import (
    User, Company, Transaction, ResearchProject, DecisionJournal,
    PortfolioPosition, ResearchOutcome, AIInsight
)
from app.services.outcome_tracking import (
    OutcomeTracker, on_buy_transaction, on_sell_transaction, get_outcome_stats
)
from app.services.research_quality import calculate_research_quality


def print_section(title):
    """Print a formatted section header"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def test_outcome_creation():
    """Test creating ResearchOutcome on BUY transaction"""
    print_section("TEST 1: Create ResearchOutcome on BUY")

    # Get test user
    user = User.query.first()
    if not user:
        print("❌ No users found. Please create a user first.")
        return False

    print(f"✓ Using user: {user.username} (ID: {user.id})")

    # Get a company with research
    company = Company.query.filter_by(user_id=user.id).first()
    if not company:
        print("❌ No companies found. Please create a company first.")
        return False

    print(f"✓ Using company: {company.ticker_symbol} - {company.name}")

    # Check for existing research
    research = ResearchProject.query.filter_by(
        user_id=user.id,
        company_id=company.id
    ).first()

    if research:
        print(f"✓ Found research project: {research.project_name} (ID: {research.id})")

        # Try to calculate research quality
        try:
            quality = calculate_research_quality(research_project_id=research.id)
            print(f"✓ Research quality score: {quality.overall_score:.1f}/100 ({quality.grade})")
            print(f"  - Questions answered: {quality.questions_answered}/{quality.questions_total}")
            print(f"  - Documents analyzed: {quality.documents_analyzed}")
            print(f"  - Research duration: {quality.research_duration_minutes} minutes")
        except Exception as e:
            print(f"⚠ Could not calculate research quality: {e}")
    else:
        print("⚠ No research project found for this company")

    # Create a test BUY transaction
    print("\n📝 Creating test BUY transaction...")

    transaction = Transaction(
        user_id=user.id,
        company_id=company.id,
        type='BUY',
        date=date.today() - timedelta(days=30),
        quantity=100,
        currency='USD',
        price_per_share=Decimal('50.00'),
        price_per_share_base=Decimal('50.00'),
        fees=Decimal('10.00'),
        fees_base=Decimal('10.00'),
        exchange_rate=Decimal('1.00'),
        exchange_rate_date=date.today() - timedelta(days=30),
        notes='Test transaction for outcome tracking'
    )

    db.session.add(transaction)
    db.session.flush()

    print(f"✓ Created transaction ID: {transaction.id}")

    # Create Decision Journal
    decision_journal = DecisionJournal(
        user_id=user.id,
        company_id=company.id,
        decision_type='BUY',
        decision_date=transaction.date,
        investment_thesis='Test thesis for outcome tracking validation',
        confidence_score=8,
        expected_return=25.0,
        expected_timeframe=12,
        is_portfolio_decision=True,
        linked_research_id=research.id if research else None
    )

    db.session.add(decision_journal)
    db.session.flush()

    print(f"✓ Created decision journal ID: {decision_journal.id}")

    # Trigger outcome tracking
    print("\n🤖 Triggering outcome tracking...")

    outcome = on_buy_transaction(
        transaction=transaction,
        decision_journal=decision_journal
    )

    if outcome:
        print(f"✅ SUCCESS! Created ResearchOutcome ID: {outcome.id}")
        print(f"\n📊 Outcome Details:")
        print(f"  - Research quality score: {outcome.research_quality_score or 'N/A'}")
        print(f"  - Questions answered: {outcome.questions_answered}/{outcome.questions_total}")
        print(f"  - Documents analyzed: {outcome.documents_analyzed}")
        print(f"  - Research duration: {outcome.research_duration_minutes} minutes")
        print(f"  - Entry price: ${outcome.entry_price}")
        print(f"  - Position size: ${outcome.position_size}")
        print(f"  - Confidence: {outcome.confidence_at_entry or 'N/A'}")
        print(f"  - Expected return: {outcome.expected_return_pct or 'N/A'}%")

        db.session.commit()
        return outcome
    else:
        print("❌ FAILED to create ResearchOutcome")
        db.session.rollback()
        return None


def test_outcome_update(outcome: ResearchOutcome):
    """Test updating ResearchOutcome on SELL transaction"""
    print_section("TEST 2: Update ResearchOutcome on SELL")

    if not outcome:
        print("❌ No outcome provided. Skipping test.")
        return False

    print(f"✓ Using ResearchOutcome ID: {outcome.id}")

    # Create a test SELL transaction
    print("\n📝 Creating test SELL transaction...")

    # Simulate holding period of 60 days
    sell_date = outcome.decision_date + timedelta(days=60)

    # Simulate 15% gain
    entry_price = float(outcome.entry_price)
    sell_price = entry_price * 1.15  # 15% gain

    transaction = Transaction(
        user_id=outcome.user_id,
        company_id=outcome.company_id,
        type='SELL',
        date=sell_date,
        quantity=100,
        currency='USD',
        price_per_share=Decimal(str(sell_price)),
        price_per_share_base=Decimal(str(sell_price)),
        fees=Decimal('10.00'),
        fees_base=Decimal('10.00'),
        exchange_rate=Decimal('1.00'),
        exchange_rate_date=sell_date,
        notes='Test SELL transaction for outcome tracking'
    )

    db.session.add(transaction)
    db.session.flush()

    print(f"✓ Created SELL transaction ID: {transaction.id}")
    print(f"  - Entry price: ${entry_price:.2f}")
    print(f"  - Sell price: ${sell_price:.2f}")

    # Calculate realized return
    realized_return_pct = ((sell_price - entry_price) / entry_price) * 100
    print(f"  - Realized return: {realized_return_pct:.1f}%")

    # Trigger outcome update
    print("\n🤖 Triggering outcome update...")

    updated_outcome = on_sell_transaction(
        transaction=transaction,
        realized_return_pct=realized_return_pct
    )

    if updated_outcome:
        print(f"✅ SUCCESS! Updated ResearchOutcome ID: {updated_outcome.id}")
        print(f"\n📊 Updated Outcome Details:")
        print(f"  - Exit date: {updated_outcome.exit_date}")
        print(f"  - Exit price: ${updated_outcome.exit_price}")
        print(f"  - Realized return: {updated_outcome.realized_return_pct:.1f}%")
        print(f"  - Hold period: {updated_outcome.actual_hold_days} days")
        print(f"  - Outcome category: {updated_outcome.outcome_category}")
        print(f"  - Thesis accuracy: {updated_outcome.thesis_accuracy_score:.1f}/100")

        db.session.commit()
        return True
    else:
        print("❌ FAILED to update ResearchOutcome")
        db.session.rollback()
        return False


def test_correlation_analysis():
    """Test correlation analysis and AIInsight generation"""
    print_section("TEST 3: Correlation Analysis & AIInsight Generation")

    user = User.query.first()
    if not user:
        print("❌ No users found.")
        return False

    # Get completed outcomes
    outcomes = ResearchOutcome.query.filter(
        ResearchOutcome.user_id == user.id,
        ResearchOutcome.realized_return_pct.isnot(None)
    ).all()

    print(f"✓ Found {len(outcomes)} completed outcomes")

    if len(outcomes) < 5:
        print(f"⚠ Need at least 5 outcomes for correlation analysis (have {len(outcomes)})")
        print("  Correlation analysis will not trigger yet.")
        return True

    # Check for generated insights
    insights = AIInsight.query.filter_by(
        user_id=user.id,
        insight_type='pattern'
    ).all()

    print(f"\n📊 Generated Insights: {len(insights)}")

    for insight in insights[-3:]:  # Show last 3 insights
        print(f"\n  • {insight.title}")
        print(f"    {insight.insight_text}")
        print(f"    Confidence: {insight.confidence:.0%}")
        print(f"    Created: {insight.created_at}")

    return True


def test_outcome_stats():
    """Test outcome statistics calculation"""
    print_section("TEST 4: Outcome Statistics")

    user = User.query.first()
    if not user:
        print("❌ No users found.")
        return False

    stats = get_outcome_stats(user.id)

    print(f"📊 User Investment Statistics:")
    print(f"\n  Total investments: {stats['total_investments']}")

    if stats['total_investments'] > 0:
        print(f"  Win rate: {stats['win_rate']:.1f}%")
        print(f"  Average return: {stats['avg_return']:.1f}%")
        print(f"  Best return: {stats['best_return']:.1f}%")
        print(f"  Worst return: {stats['worst_return']:.1f}%")
        print(f"  Average hold days: {stats['avg_hold_days']:.0f}")

        if stats['research_advantage_pct'] is not None:
            print(f"\n  Research advantage: {stats['research_advantage_pct']:.1f}%")
            print(f"  (Researched investments perform {stats['research_advantage_pct']:.1f}% better)")

        print(f"\n  Average research quality: {stats['avg_research_quality']:.1f}/100")

        print(f"\n  Outcome Breakdown:")
        breakdown = stats['outcome_breakdown']
        print(f"    Big wins (≥25%): {breakdown['big_wins']}")
        print(f"    Small wins (5-25%): {breakdown['small_wins']}")
        print(f"    Break even (-5% to 5%): {breakdown['break_even']}")
        print(f"    Small losses (-25% to -5%): {breakdown['small_losses']}")
        print(f"    Big losses (<-25%): {breakdown['big_losses']}")
    else:
        print("  No completed investments yet.")

    return True


def main():
    """Run all tests"""
    app = create_app()

    with app.app_context():
        print("\n" + "="*70)
        print("  AI OUTCOME TRACKING SYSTEM - INTEGRATION TEST")
        print("="*70)

        try:
            # Test 1: Create outcome on BUY
            outcome = test_outcome_creation()

            if outcome:
                # Test 2: Update outcome on SELL
                test_outcome_update(outcome)

            # Test 3: Correlation analysis
            test_correlation_analysis()

            # Test 4: Outcome statistics
            test_outcome_stats()

            print_section("TEST SUMMARY")
            print("✅ All tests completed!")
            print("\nNext steps:")
            print("1. Make some real BUY transactions in the app")
            print("2. Verify ResearchOutcome records are created")
            print("3. Make SELL transactions to complete the cycle")
            print("4. Check for AIInsight generation after 5+ outcomes")

        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()


if __name__ == '__main__':
    main()
