"""
Outcome Tracking Service

Links research quality to investment outcomes.
This is the core feedback loop that enables learning from investment results.

Lifecycle:
1. User completes research (ResearchSession or ResearchProject)
2. User makes BUY transaction → OutcomeTracker.create_outcome_record()
3. Position is held, current_return_pct updated periodically
4. User makes SELL transaction → OutcomeTracker.update_outcome_on_sell()
5. Correlation analysis runs to identify patterns

Usage:
    from app.services.outcome_tracking import OutcomeTracker, on_buy_transaction, on_sell_transaction
    
    # Called from portfolio transaction routes
    on_buy_transaction(transaction, decision_journal)
    on_sell_transaction(transaction, realized_return_pct)
    
    # Or use the tracker directly
    tracker = OutcomeTracker()
    outcome = tracker.create_outcome_record(user_id, company_id, ...)
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, date
from decimal import Decimal
import logging

from app import db
from app.utils.time_utils import now_utc
from app.models.ai_intelligence import ResearchOutcome, AIInsight
from .research_quality import calculate_research_quality, get_research_quality_for_company

logger = logging.getLogger(__name__)


class OutcomeTracker:
    """
    Tracks and correlates research quality with investment outcomes.
    
    This is the core service for the Phase 1 feedback loop:
    Research → Decision → Transaction → Outcome → Learning
    """
    
    # Outcome categories based on return percentage
    OUTCOME_THRESHOLDS = {
        'big_win': 25,      # >= 25% return
        'small_win': 5,     # >= 5% return
        'break_even': -5,   # >= -5% return
        'small_loss': -25,  # >= -25% return
        'big_loss': float('-inf')  # < -25% return
    }
    
    def create_outcome_record(
        self,
        user_id: int,
        company_id: int,
        transaction: 'Transaction',
        decision_journal: Optional['DecisionJournal'] = None,
        research_session_id: Optional[int] = None,
        research_project_id: Optional[int] = None
    ) -> ResearchOutcome:
        """
        Create outcome record when user makes a BUY transaction.
        
        Called automatically from portfolio transaction flow.
        
        Args:
            user_id: User ID
            company_id: Company ID
            transaction: The BUY Transaction object
            decision_journal: Optional linked DecisionJournal
            research_session_id: Optional specific research session
            research_project_id: Optional specific research project
            
        Returns:
            Created ResearchOutcome record
        """
        from app.models import ResearchSession, ResearchProject, DecisionJournal, DestinationCheckpoint
        
        # Find linked research if not provided
        if not research_session_id and not research_project_id:
            # Check DecisionJournal for linked research
            if decision_journal and hasattr(decision_journal, 'linked_research_id'):
                research_project_id = decision_journal.linked_research_id
            
            # Try to find most recent completed research for this company
            if not research_project_id:
                project = ResearchProject.query.filter_by(
                    user_id=user_id,
                    company_id=company_id,
                    status='completed'
                ).order_by(ResearchProject.created_at.desc()).first()
                
                if project:
                    research_project_id = project.id
            
            if not research_session_id and not research_project_id:
                session = ResearchSession.query.filter_by(
                    user_id=user_id,
                    company_id=company_id,
                    status='completed'
                ).order_by(ResearchSession.created_at.desc()).first()
                
                if session:
                    research_session_id = session.id
        
        # Calculate research quality
        quality_score = None
        quality_data = None
        
        if research_project_id or research_session_id:
            quality_data = calculate_research_quality(
                research_session_id=research_session_id,
                research_project_id=research_project_id
            )
            quality_score = quality_data
        
        # Get checkpoint count for this company
        checkpoints = DestinationCheckpoint.query.filter_by(
            company_id=company_id,
            user_id=user_id
        ).all()
        
        # Extract thesis and confidence from decision journal
        initial_thesis = None
        confidence_at_entry = None
        expected_return_pct = None
        expected_hold_months = None
        
        if decision_journal:
            initial_thesis = decision_journal.investment_thesis
            confidence_at_entry = decision_journal.confidence_level
            # Try to get expected return/hold from decision journal if available
            if hasattr(decision_journal, 'expected_return'):
                expected_return_pct = decision_journal.expected_return
            if hasattr(decision_journal, 'expected_hold_period'):
                expected_hold_months = decision_journal.expected_hold_period
        
        # Create the outcome record
        outcome = ResearchOutcome(
            user_id=user_id,
            company_id=company_id,
            research_session_id=research_session_id,
            project_id=research_project_id,
            decision_journal_id=decision_journal.id if decision_journal else None,
            
            # Research metrics
            research_quality_score=quality_score.overall_score if quality_score else None,
            questions_answered=quality_score.questions_answered if quality_score else 0,
            questions_total=quality_score.questions_total if quality_score else 0,
            documents_analyzed=quality_score.documents_analyzed if quality_score else 0,
            research_duration_minutes=quality_score.research_duration_minutes if quality_score else 0,
            checklist_completion_pct=(
                (quality_score.questions_answered / quality_score.questions_total * 100)
                if quality_score and quality_score.questions_total > 0 else 0
            ),
            
            # Research depth indicators
            had_financial_analysis=quality_score.had_financial_analysis if quality_score else False,
            had_competitive_analysis=quality_score.had_competitive_analysis if quality_score else False,
            had_management_review=quality_score.had_management_review if quality_score else False,
            had_valuation_model=quality_score.had_valuation_model if quality_score else False,
            
            # Decision metrics
            decision_date=transaction.transaction_date,
            entry_price=transaction.price_per_share,
            position_size=transaction.total_value,
            initial_thesis=initial_thesis,
            confidence_at_entry=confidence_at_entry,
            expected_return_pct=expected_return_pct,
            expected_hold_months=expected_hold_months,
            
            # Initialize outcome metrics
            checkpoints_total=len(checkpoints),
            thesis_still_valid=True,

            created_at=now_utc()
        )
        
        db.session.add(outcome)
        db.session.commit()
        
        logger.info(
            f"Created ResearchOutcome {outcome.id} for company {company_id} "
            f"(quality_score={quality_score.overall_score if quality_score else 'N/A'})"
        )
        
        return outcome
    
    def update_outcome_on_sell(
        self,
        user_id: int,
        company_id: int,
        sell_transaction: 'Transaction',
        realized_return_pct: float
    ) -> Optional[ResearchOutcome]:
        """
        Update outcome record when user sells a position.
        
        Args:
            user_id: User ID
            company_id: Company ID
            sell_transaction: The SELL Transaction object
            realized_return_pct: Realized return percentage
            
        Returns:
            Updated ResearchOutcome or None if not found
        """
        from app.models import DestinationCheckpoint
        
        # Find the open outcome record for this position
        outcome = ResearchOutcome.query.filter_by(
            user_id=user_id,
            company_id=company_id,
            exit_date=None  # Not yet closed
        ).order_by(ResearchOutcome.decision_date.desc()).first()
        
        if not outcome:
            logger.warning(f"No open outcome record found for company {company_id}")
            return None
        
        # Calculate thesis accuracy
        thesis_accuracy = self._calculate_thesis_accuracy(outcome, realized_return_pct)
        
        # Get checkpoint metrics
        checkpoints = DestinationCheckpoint.query.filter_by(
            company_id=company_id,
            user_id=user_id
        ).all()
        
        met_checkpoints = len([c for c in checkpoints if c.status == 'met'])
        
        # Categorize outcome
        outcome_category = self._categorize_outcome(realized_return_pct)
        
        # Calculate hold period
        actual_hold_days = None
        if outcome.decision_date:
            hold_delta = sell_transaction.transaction_date - outcome.decision_date
            actual_hold_days = hold_delta.days
        
        # Update the record
        outcome.exit_date = sell_transaction.transaction_date
        outcome.exit_price = sell_transaction.price_per_share
        outcome.realized_return_pct = realized_return_pct
        outcome.actual_hold_days = actual_hold_days
        
        outcome.thesis_accuracy_score = thesis_accuracy
        outcome.checkpoints_met = met_checkpoints
        outcome.checkpoints_total = len(checkpoints)
        
        outcome.outcome_category = outcome_category
        outcome.outcome_recorded_at = now_utc()
        outcome.last_updated_at = now_utc()
        
        db.session.commit()
        
        logger.info(
            f"Updated ResearchOutcome {outcome.id}: {outcome_category} "
            f"({realized_return_pct:.1f}%, held {actual_hold_days} days)"
        )
        
        # Trigger correlation analysis if we have enough data
        self._check_and_run_correlation_analysis(user_id)
        
        return outcome
    
    def update_current_return(
        self,
        outcome_id: int,
        current_return_pct: float
    ) -> Optional[ResearchOutcome]:
        """
        Update the current return percentage for an open position.
        
        Called periodically to track unrealized returns.
        
        Args:
            outcome_id: ResearchOutcome ID
            current_return_pct: Current unrealized return percentage
            
        Returns:
            Updated ResearchOutcome or None
        """
        outcome = ResearchOutcome.query.get(outcome_id)
        
        if not outcome:
            return None
        
        if outcome.exit_date:
            logger.warning(f"Outcome {outcome_id} is already closed")
            return outcome
        
        outcome.current_return_pct = current_return_pct
        outcome.last_updated_at = now_utc()
        
        db.session.commit()
        return outcome
    
    def _calculate_thesis_accuracy(
        self,
        outcome: ResearchOutcome,
        realized_return: float
    ) -> float:
        """
        Calculate how accurate the initial thesis was.
        
        Based on:
        - Expected return vs actual (40%)
        - Hold period accuracy (30%)
        - Checkpoint hit rate (30%)
        """
        scores = []
        weights = []
        
        # 1. Return expectation accuracy (40%)
        if outcome.expected_return_pct is not None:
            expected = float(outcome.expected_return_pct)
            actual = realized_return
            
            # Same direction = partial credit
            if (expected > 0 and actual > 0) or (expected < 0 and actual < 0):
                # Score based on how close
                diff = abs(expected - actual)
                accuracy = max(0, 100 - diff * 2)  # -2 points per % difference
                scores.append(accuracy)
            else:
                # Wrong direction
                scores.append(20)
            weights.append(0.4)
        
        # 2. Hold period accuracy (30%)
        if outcome.expected_hold_months and outcome.actual_hold_days:
            expected_days = outcome.expected_hold_months * 30
            actual_days = outcome.actual_hold_days
            
            ratio = min(expected_days, actual_days) / max(expected_days, actual_days)
            scores.append(ratio * 100)
            weights.append(0.3)
        
        # 3. Checkpoint accuracy (30%)
        if outcome.checkpoints_total and outcome.checkpoints_total > 0:
            checkpoint_pct = (outcome.checkpoints_met or 0) / outcome.checkpoints_total
            scores.append(checkpoint_pct * 100)
            weights.append(0.3)
        
        # Calculate weighted average
        if scores:
            total_weight = sum(weights)
            weighted_sum = sum(s * w for s, w in zip(scores, weights))
            return weighted_sum / total_weight
        
        return 50.0  # Default neutral score
    
    def _categorize_outcome(self, return_pct: float) -> str:
        """Categorize outcome based on return percentage"""
        if return_pct >= self.OUTCOME_THRESHOLDS['big_win']:
            return 'big_win'
        elif return_pct >= self.OUTCOME_THRESHOLDS['small_win']:
            return 'small_win'
        elif return_pct >= self.OUTCOME_THRESHOLDS['break_even']:
            return 'break_even'
        elif return_pct >= self.OUTCOME_THRESHOLDS['small_loss']:
            return 'small_loss'
        else:
            return 'big_loss'
    
    def _check_and_run_correlation_analysis(self, user_id: int):
        """
        Check if we have enough data and run correlation analysis.
        
        Creates AI insights if meaningful patterns are found.
        """
        # Get completed outcomes
        outcomes = ResearchOutcome.query.filter(
            ResearchOutcome.user_id == user_id,
            ResearchOutcome.realized_return_pct.isnot(None)
        ).all()
        
        if len(outcomes) < 5:
            # Not enough data for meaningful correlation
            logger.debug(f"Only {len(outcomes)} outcomes for user {user_id}, need at least 5")
            return
        
        # Analyze correlation between research quality and returns
        high_quality = [o for o in outcomes if (o.research_quality_score or 0) >= 70]
        low_quality = [o for o in outcomes if (o.research_quality_score or 0) < 70]
        
        if high_quality and low_quality:
            high_avg = sum(o.realized_return_pct for o in high_quality) / len(high_quality)
            low_avg = sum(o.realized_return_pct for o in low_quality) / len(low_quality)
            
            difference = high_avg - low_avg
            
            if difference > 5:  # Meaningful difference (>5%)
                # Create an insight
                insight = AIInsight(
                    user_id=user_id,
                    insight_type='pattern',
                    trigger_type='periodic',
                    context_type='portfolio',
                    title='Research Quality Correlates with Returns',
                    insight_text=(
                        f"Your high-quality research (score 70+) has averaged {high_avg:.1f}% returns, "
                        f"while lower-quality research averaged {low_avg:.1f}% returns. "
                        f"That's a {difference:.1f}% difference! This suggests your thorough research pays off."
                    ),
                    supporting_data={
                        'high_quality_avg_return': high_avg,
                        'low_quality_avg_return': low_avg,
                        'difference': difference,
                        'high_quality_count': len(high_quality),
                        'low_quality_count': len(low_quality),
                        'total_outcomes': len(outcomes)
                    },
                    ai_provider='rule_based',
                    confidence=min(0.9, 0.5 + len(outcomes) * 0.05),  # Higher confidence with more data
                    is_active=True,
                    created_at=now_utc()
                )
                
                db.session.add(insight)
                db.session.commit()
                
                logger.info(
                    f"Created correlation insight for user {user_id}: "
                    f"high_quality={high_avg:.1f}%, low_quality={low_avg:.1f}%"
                )
    
    def get_user_outcome_stats(self, user_id: int) -> Dict[str, Any]:
        """
        Get summary statistics for a user's outcomes.
        
        Returns:
            Dict with stats like win_rate, avg_return, etc.
        """
        outcomes = ResearchOutcome.query.filter(
            ResearchOutcome.user_id == user_id,
            ResearchOutcome.realized_return_pct.isnot(None)
        ).all()
        
        if not outcomes:
            return {
                'total_investments': 0,
                'win_rate': None,
                'avg_return': None,
                'research_correlation': None
            }
        
        wins = [o for o in outcomes if o.realized_return_pct > 0]
        
        # Calculate research correlation
        researched = [o for o in outcomes if o.research_quality_score and o.research_quality_score > 0]
        unreasearched = [o for o in outcomes if not o.research_quality_score or o.research_quality_score == 0]
        
        research_advantage = None
        if researched and unreasearched:
            researched_avg = sum(o.realized_return_pct for o in researched) / len(researched)
            unreasearched_avg = sum(o.realized_return_pct for o in unreasearched) / len(unreasearched)
            research_advantage = researched_avg - unreasearched_avg
        
        return {
            'total_investments': len(outcomes),
            'win_rate': len(wins) / len(outcomes) * 100,
            'avg_return': sum(o.realized_return_pct for o in outcomes) / len(outcomes),
            'best_return': max(o.realized_return_pct for o in outcomes),
            'worst_return': min(o.realized_return_pct for o in outcomes),
            'avg_hold_days': sum(o.actual_hold_days or 0 for o in outcomes) / len(outcomes),
            'research_advantage_pct': research_advantage,
            'avg_research_quality': (
                sum(o.research_quality_score or 0 for o in outcomes) / len(outcomes)
            ),
            'outcome_breakdown': {
                'big_wins': len([o for o in outcomes if o.outcome_category == 'big_win']),
                'small_wins': len([o for o in outcomes if o.outcome_category == 'small_win']),
                'break_even': len([o for o in outcomes if o.outcome_category == 'break_even']),
                'small_losses': len([o for o in outcomes if o.outcome_category == 'small_loss']),
                'big_losses': len([o for o in outcomes if o.outcome_category == 'big_loss']),
            }
        }


# ============================================================
# Integration Functions - Called from Portfolio Routes
# ============================================================

def on_buy_transaction(
    transaction: 'Transaction',
    decision_journal: Optional['DecisionJournal'] = None
) -> Optional[ResearchOutcome]:
    """
    Hook called when user makes a BUY transaction.
    
    Creates a ResearchOutcome record linking research to this investment.
    
    Args:
        transaction: The BUY Transaction object
        decision_journal: Optional linked DecisionJournal
        
    Returns:
        Created ResearchOutcome or None if error
    """
    try:
        tracker = OutcomeTracker()
        return tracker.create_outcome_record(
            user_id=transaction.user_id,
            company_id=transaction.company_id,
            transaction=transaction,
            decision_journal=decision_journal
        )
    except Exception as e:
        logger.error(f"Error creating outcome record: {e}")
        return None


def on_sell_transaction(
    transaction: 'Transaction',
    realized_return_pct: float
) -> Optional[ResearchOutcome]:
    """
    Hook called when user makes a SELL transaction.
    
    Updates the ResearchOutcome record with final outcome data.
    
    Args:
        transaction: The SELL Transaction object
        realized_return_pct: Realized return percentage
        
    Returns:
        Updated ResearchOutcome or None if not found/error
    """
    try:
        tracker = OutcomeTracker()
        return tracker.update_outcome_on_sell(
            user_id=transaction.user_id,
            company_id=transaction.company_id,
            sell_transaction=transaction,
            realized_return_pct=realized_return_pct
        )
    except Exception as e:
        logger.error(f"Error updating outcome on sell: {e}")
        return None


def get_outcome_stats(user_id: int) -> Dict[str, Any]:
    """
    Get outcome statistics for a user.
    
    Convenience function for dashboards and analytics.
    """
    tracker = OutcomeTracker()
    return tracker.get_user_outcome_stats(user_id)