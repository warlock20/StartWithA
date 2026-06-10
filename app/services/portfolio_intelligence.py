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
Portfolio Intelligence Service

Provides insights and analytics on portfolio performance,
correlating research quality with investment outcomes.

This is the "learning layer" that helps investors understand:
- Does better research lead to better returns?
- What patterns exist in their winning/losing trades?
- Are they improving over time?

Usage:
    from app.services.portfolio_intelligence import PortfolioIntelligenceService
    
    service = PortfolioIntelligenceService(user_id=123)
    correlation_data = service.get_correlation_data()
    checkpoints = service.get_upcoming_checkpoints()
    insights = service.get_learning_insights()
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
import logging

from sqlalchemy.orm import joinedload

from app import db, cache
from app.utils.time_utils import now_utc
from app.utils.financial_utils import calculate_cagr

from app.models.ai_intelligence import ResearchOutcome
from app.models import DecisionJournal, PortfolioPosition, DestinationCheckpoint, Company

logger = logging.getLogger(__name__)

# Thresholds for outcome analysis (days)
SHORT_HOLD_THRESHOLD_DAYS = 90
# Minimum data points needed for confidence-return correlation
MIN_CONFIDENCE_RETURN_SAMPLES = 3


@dataclass
class GradePerformance:
    """Performance metrics for a quality grade"""
    grade: str
    count: int
    avg_return: float
    win_rate: float
    avg_hold_days: int


@dataclass
class CorrelationData:
    """Research quality to returns correlation data"""
    # By grade breakdown
    grade_performance: List[GradePerformance]
    
    # Overall metrics
    total_outcomes: int
    researched_count: int
    non_researched_count: int
    
    # Averages
    researched_avg_return: float
    non_researched_avg_return: float
    research_advantage: float  # Difference between researched and non-researched
    
    # Quality correlation
    correlation_coefficient: Optional[float]  # -1 to 1, how correlated is quality to returns
    
    # Best/Worst
    best_grade: Optional[str]
    worst_grade: Optional[str]
    
    # Enough data?
    has_sufficient_data: bool
    min_data_message: Optional[str]


@dataclass
class CheckpointReminder:
    """A checkpoint reminder for display"""
    id: int
    company_name: str
    company_ticker: str
    company_id: int
    metric: str            # E.g., "Quarterly Revenue", "EPS"
    expectation: str       # E.g., ">$5 Billion", "Beat estimates"
    description: str
    target_date: date
    status: str  # 'overdue', 'this_week', 'upcoming'
    days_until: int  # negative if overdue
    checkpoint_type: Optional[str]
    metric_target: Optional[str]


@dataclass
class ThesisReality:
    """Comparison of thesis expectations vs actual performance"""
    company_name: str
    company_ticker: str
    company_id: int
    position_id: int

    # Original thesis
    investment_thesis: str
    expected_return: Optional[float]
    expected_timeframe_months: Optional[int]
    confidence_score: Optional[int]

    # Reality
    actual_return_pct: float
    annualized_return_pct: float  # CAGR - Compound Annual Growth Rate
    days_held: int
    current_price: Optional[Decimal]

    # Assessment
    status: str  # 'on_track', 'exceeding', 'behind', 'needs_attention'
    thesis_still_valid: Optional[bool]


@dataclass
class LearningInsight:
    """A learning insight derived from user's data"""
    category: str  # 'winning_pattern', 'warning', 'edge', 'improvement'
    title: str
    description: str
    supporting_data: Optional[str]
    importance: str  # 'high', 'medium', 'low'


class PortfolioIntelligenceService:
    """
    Main service for portfolio intelligence and learning insights.
    """
    
    # Thresholds (will be configurable later)
    MIN_OUTCOMES_FOR_ANALYSIS = 3
    MIN_OUTCOMES_PER_GRADE = 1
    HIGH_QUALITY_THRESHOLD = 70  # Score >= 70 is "researched"
    
    def __init__(self, user_id: int):
        self.user_id = user_id
    
    # =========================================================================
    # STEP 1: Correlation Dashboard
    # =========================================================================
    
    def get_correlation_data(self) -> CorrelationData:
        """
        Get research quality to returns correlation data.
        
        Returns:
            CorrelationData with grade breakdown, averages, and correlation metrics
        """
        # Get all completed outcomes for this user
        outcomes = ResearchOutcome.query.filter(
            ResearchOutcome.user_id == self.user_id,
            ResearchOutcome.realized_return_pct.isnot(None)
        ).all()
        
        # Check if we have enough data
        if len(outcomes) < self.MIN_OUTCOMES_FOR_ANALYSIS:
            return CorrelationData(
                grade_performance=[],
                total_outcomes=len(outcomes),
                researched_count=0,
                non_researched_count=0,
                researched_avg_return=0.0,
                non_researched_avg_return=0.0,
                research_advantage=0.0,
                correlation_coefficient=None,
                best_grade=None,
                worst_grade=None,
                has_sufficient_data=False,
                min_data_message=f"Need at least {self.MIN_OUTCOMES_FOR_ANALYSIS} completed trades to analyze. You have {len(outcomes)}."
            )
        
        # Group by grade
        grade_buckets = {'A': [], 'B': [], 'C': [], 'D': [], 'F': []}
        researched_returns = []
        non_researched_returns = []
        
        for outcome in outcomes:
            grade = self._score_to_grade(outcome.research_quality_score or 0)
            return_pct = float(outcome.realized_return_pct)
            
            grade_buckets[grade].append({
                'return': return_pct,
                'hold_days': (outcome.exit_date - outcome.entry_date).days if outcome.exit_date and outcome.entry_date else 0,
                'won': return_pct > 0
            })
            
            # Split into researched vs non-researched
            if (outcome.research_quality_score or 0) >= self.HIGH_QUALITY_THRESHOLD:
                researched_returns.append(return_pct)
            else:
                non_researched_returns.append(return_pct)
        
        # Calculate grade performance
        grade_performance = []
        for grade in ['A', 'B', 'C', 'D', 'F']:
            bucket = grade_buckets[grade]
            if len(bucket) >= self.MIN_OUTCOMES_PER_GRADE:
                returns = [b['return'] for b in bucket]
                hold_days = [b['hold_days'] for b in bucket]
                wins = [b['won'] for b in bucket]
                
                grade_performance.append(GradePerformance(
                    grade=grade,
                    count=len(bucket),
                    avg_return=round(sum(returns) / len(returns), 1),
                    win_rate=round(sum(wins) / len(wins) * 100, 1),
                    avg_hold_days=round(sum(hold_days) / len(hold_days)) if hold_days else 0
                ))
        
        # Calculate averages
        researched_avg = sum(researched_returns) / len(researched_returns) if researched_returns else 0
        non_researched_avg = sum(non_researched_returns) / len(non_researched_returns) if non_researched_returns else 0
        research_advantage = researched_avg - non_researched_avg
        
        # Find best/worst grades
        best_grade = None
        worst_grade = None
        if grade_performance:
            sorted_by_return = sorted(grade_performance, key=lambda x: x.avg_return, reverse=True)
            best_grade = sorted_by_return[0].grade
            worst_grade = sorted_by_return[-1].grade
        
        # Calculate correlation coefficient (Pearson)
        correlation = self._calculate_correlation(outcomes)
        
        return CorrelationData(
            grade_performance=grade_performance,
            total_outcomes=len(outcomes),
            researched_count=len(researched_returns),
            non_researched_count=len(non_researched_returns),
            researched_avg_return=round(researched_avg, 1),
            non_researched_avg_return=round(non_researched_avg, 1),
            research_advantage=round(research_advantage, 1),
            correlation_coefficient=correlation,
            best_grade=best_grade,
            worst_grade=worst_grade,
            has_sufficient_data=True,
            min_data_message=None
        )
    
    def _calculate_correlation(self, outcomes) -> Optional[float]:
        """Calculate Pearson correlation between quality score and returns"""
        if len(outcomes) < 3:
            return None
        
        scores = []
        returns = []
        
        for outcome in outcomes:
            if outcome.research_quality_score is not None and outcome.realized_return_pct is not None:
                scores.append(float(outcome.research_quality_score))
                returns.append(float(outcome.realized_return_pct))
        
        if len(scores) < 3:
            return None
        
        # Calculate Pearson correlation
        n = len(scores)
        sum_x = sum(scores)
        sum_y = sum(returns)
        sum_xy = sum(x * y for x, y in zip(scores, returns))
        sum_x2 = sum(x ** 2 for x in scores)
        sum_y2 = sum(y ** 2 for y in returns)
        
        numerator = n * sum_xy - sum_x * sum_y
        denominator = ((n * sum_x2 - sum_x ** 2) * (n * sum_y2 - sum_y ** 2)) ** 0.5
        
        if denominator == 0:
            return None
        
        correlation = numerator / denominator
        return round(correlation, 2)
    
    def _score_to_grade(self, score: float) -> str:
        """Convert numeric score to letter grade"""
        if score >= 90:
            return 'A'
        elif score >= 80:
            return 'B'
        elif score >= 70:
            return 'C'
        elif score >= 60:
            return 'D'
        else:
            return 'F'
    
    # =========================================================================
    # STEP 2: Checkpoint Reminders
    # =========================================================================
    
    def get_upcoming_checkpoints(self, days_ahead: int = 30) -> Dict[str, List[CheckpointReminder]]:
        """
        Get upcoming and overdue checkpoints grouped by urgency.
        
        Args:
            days_ahead: How many days ahead to look
            
        Returns:
            Dict with keys 'overdue', 'this_week', 'upcoming'
        """
        today = now_utc().date()
        week_from_now = today + timedelta(days=7)
        month_from_now = today + timedelta(days=30)
        three_months_from_now = today + timedelta(days=90)

        # Get active checkpoints for companies in portfolio
        from sqlalchemy import select
        portfolio_company_ids_query = select(PortfolioPosition.company_id).filter(
            PortfolioPosition.user_id == self.user_id,
            PortfolioPosition.is_active == True
        ).scalar_subquery()

        # Get ALL active checkpoints with eager-loaded company (avoid N+1)
        checkpoints = DestinationCheckpoint.query.filter(
            DestinationCheckpoint.user_id == self.user_id,
            DestinationCheckpoint.company_id.in_(portfolio_company_ids_query),
            DestinationCheckpoint.status == 'Active'
        ).options(
            joinedload(DestinationCheckpoint.company)
        ).order_by(DestinationCheckpoint.target_date.asc()).all()

        result = {
            'overdue': [],
            'this_week': [],
            'this_month': [],
            'next_3_months': [],
            'beyond': []
        }

        for cp in checkpoints:
            days_until = (cp.target_date - today).days

            if days_until < 0:
                status = 'overdue'
            elif days_until <= 7:
                status = 'this_week'
            elif days_until <= 30:
                status = 'this_month'
            elif days_until <= 90:
                status = 'next_3_months'
            else:
                status = 'beyond'
            
            reminder = CheckpointReminder(
                id=cp.id,
                company_name=cp.company.name if cp.company else 'Unknown',
                company_ticker=cp.company.ticker_symbol if cp.company else '???',
                company_id=cp.company_id,
                description='',  # DestinationCheckpoint doesn't have description field
                target_date=cp.target_date,
                metric=cp.metric or '',
                expectation=cp.expectation or '',
                status=status,
                days_until=days_until,
                checkpoint_type=cp.checkpoint_type if hasattr(cp, 'checkpoint_type') else None,
                metric_target=cp.metric_target if hasattr(cp, 'metric_target') else None
            )
            
            result[status].append(reminder)
        
        return result
    
    def get_checkpoint_summary(self) -> Dict[str, Any]:
        """Get a quick summary of checkpoint status"""
        checkpoints = self.get_upcoming_checkpoints()

        return {
            'overdue_count': len(checkpoints['overdue']),
            'this_week_count': len(checkpoints['this_week']),
            'this_month_count': len(checkpoints['this_month']),
            'next_3_months_count': len(checkpoints['next_3_months']),
            'beyond_count': len(checkpoints['beyond']),
            'total_active': sum(len(v) for v in checkpoints.values()),
            'needs_attention': len(checkpoints['overdue']) > 0
        }
    
    # =========================================================================
    # STEP 3: Position Monitoring (Thesis vs Reality)
    # =========================================================================
    
    def get_thesis_reality_check(self) -> List[ThesisReality]:
        """
        Compare original investment thesis to actual performance.
        Uses CAGR (annualized returns) for fair comparison across different holding periods.

        Returns:
            List of ThesisReality for each active position
        """
        # Get active positions with eager-loaded company+sector
        positions = PortfolioPosition.query.filter_by(
            user_id=self.user_id,
            is_active=True
        ).options(
            joinedload(PortfolioPosition.company).joinedload(Company.sector)
        ).all()

        if not positions:
            return []

        # Batch load all BUY decision journals for these companies (avoids N+1)
        company_ids = [p.company_id for p in positions]
        all_journals = DecisionJournal.query.filter(
            DecisionJournal.user_id == self.user_id,
            DecisionJournal.company_id.in_(company_ids),
            DecisionJournal.decision_type == 'BUY',
            DecisionJournal.is_portfolio_decision == True
        ).order_by(DecisionJournal.decision_date.desc()).all()
        # Keep most recent journal per company
        journals_map = {}
        for j in all_journals:
            if j.company_id not in journals_map:
                journals_map[j.company_id] = j

        results = []

        for position in positions:
            journal = journals_map.get(position.company_id)

            # Calculate actual returns
            actual_return = float(position.unrealized_gain_loss_pct or 0)
            days_held = position.days_held or 0
            annualized_return = calculate_cagr(actual_return, days_held)

            # Determine status (using annualized return for fair comparison)
            status = self._assess_thesis_status(
                expected_return=journal.expected_return if journal else None,
                expected_timeframe=journal.expected_timeframe if journal else None,
                annualized_return=annualized_return,
                total_return=actual_return,
                days_held=days_held
            )

            results.append(ThesisReality(
                company_name=position.company.name if position.company else 'Unknown',
                company_ticker=position.company.ticker_symbol if position.company else '???',
                company_id=position.company_id,
                position_id=position.id,
                investment_thesis=journal.investment_thesis if journal else 'No thesis recorded',
                expected_return=journal.expected_return if journal else None,
                expected_timeframe_months=journal.expected_timeframe if journal else None,
                confidence_score=journal.confidence_score if journal else None,
                actual_return_pct=actual_return,
                annualized_return_pct=annualized_return,
                days_held=days_held,
                current_price=position.current_price,
                status=status,
                thesis_still_valid=None  # User needs to assess this
            ))

        # Sort by status (needs_attention first)
        status_order = {'needs_attention': 0, 'behind': 1, 'on_track': 2, 'exceeding': 3}
        results.sort(key=lambda x: status_order.get(x.status, 99))

        return results
    
    def _assess_thesis_status(
        self,
        expected_return: Optional[float],
        expected_timeframe: Optional[int],
        annualized_return: float,
        total_return: float,
        days_held: int
    ) -> str:
        """
        Assess how the position is tracking vs expectations using CAGR.

        Args:
            expected_return: Expected return % (assumed to be annualized if timeframe given)
            expected_timeframe: Expected timeframe in months
            annualized_return: CAGR of the position
            total_return: Total return % (for short-term positions)
            days_held: Days the position has been held

        Returns:
            Status: 'exceeding', 'on_track', 'behind', or 'needs_attention'
        """

        if expected_return is None:
            # No expectations set - use annualized return thresholds
            if annualized_return >= 20:
                return 'exceeding'
            elif annualized_return >= 0:
                return 'on_track'
            elif annualized_return >= -10:
                return 'behind'
            else:
                return 'needs_attention'

        # For positions held < 30 days, use total return for comparison
        # (annualized returns are misleading for very short periods)
        if days_held < 30:
            comparison_return = total_return
            # Scale expected return proportionally for short holding period
            if expected_timeframe:
                months_held = days_held / 30
                expected_comparison = expected_return * (months_held / expected_timeframe)
            else:
                expected_comparison = expected_return * 0.1  # Assume 10% of expected
        else:
            # Use annualized returns for fair comparison
            comparison_return = annualized_return
            expected_comparison = expected_return

        # Compare actual to expected
        if comparison_return >= expected_comparison * 1.2:
            return 'exceeding'  # Beating expectations by 20%+
        elif comparison_return >= expected_comparison * 0.8:
            return 'on_track'  # Within 80-120% of expectations
        elif comparison_return >= 0:
            return 'behind'  # Positive but below expectations
        else:
            return 'needs_attention'  # Losing money
    
    # =========================================================================
    # STEP 4: Learning Insights
    # =========================================================================
    
    def get_learning_insights(self) -> List[LearningInsight]:
        """
        Generate personalized learning insights from user's trading data.

        Returns:
            List of LearningInsight sorted by importance
        """
        insights = []

        # Get all outcomes with eager-loaded company+sector (avoids N+1 in sector analysis)
        outcomes = ResearchOutcome.query.filter(
            ResearchOutcome.user_id == self.user_id,
            ResearchOutcome.realized_return_pct.isnot(None)
        ).options(
            joinedload(ResearchOutcome.company).joinedload(Company.sector)
        ).all()

        if len(outcomes) < 3:
            insights.append(LearningInsight(
                category='improvement',
                title='Build Your Track Record',
                description=f'Complete more trades to unlock personalized insights. You have {len(outcomes)} completed trades, need at least 3.',
                supporting_data=None,
                importance='medium'
            ))
            return insights

        # Batch load BUY decision journals for confidence calibration (avoids N+1)
        company_ids = [o.company_id for o in outcomes]
        journals = DecisionJournal.query.filter(
            DecisionJournal.user_id == self.user_id,
            DecisionJournal.company_id.in_(company_ids),
            DecisionJournal.decision_type == 'BUY',
            DecisionJournal.is_portfolio_decision == True
        ).all()
        journals_by_company = {}
        for j in journals:
            journals_by_company[j.company_id] = j

        # Analyze patterns
        insights.extend(self._analyze_quality_patterns(outcomes))
        insights.extend(self._analyze_holding_patterns(outcomes))
        insights.extend(self._analyze_confidence_calibration(outcomes, journals_by_company))
        insights.extend(self._analyze_sector_patterns(outcomes))
        
        # Sort by importance
        importance_order = {'high': 0, 'medium': 1, 'low': 2}
        insights.sort(key=lambda x: importance_order.get(x.importance, 99))
        
        return insights[:6]  # Return top 6 insights
    
    def _analyze_quality_patterns(self, outcomes) -> List[LearningInsight]:
        """Analyze research quality patterns"""
        insights = []
        
        high_quality = [o for o in outcomes if (o.research_quality_score or 0) >= 70]
        low_quality = [o for o in outcomes if (o.research_quality_score or 0) < 70]
        
        if high_quality and low_quality:
            hq_avg = sum(float(o.realized_return_pct) for o in high_quality) / len(high_quality)
            lq_avg = sum(float(o.realized_return_pct) for o in low_quality) / len(low_quality)
            
            if hq_avg > lq_avg + 5:
                insights.append(LearningInsight(
                    category='edge',
                    title='Research Quality Is Your Edge',
                    description=f'High-quality research (score 70+) delivers {hq_avg - lq_avg:.1f}% better returns than low-quality research.',
                    supporting_data=f'High quality: {hq_avg:.1f}% avg, Low quality: {lq_avg:.1f}% avg',
                    importance='high'
                ))
            elif lq_avg > hq_avg:
                insights.append(LearningInsight(
                    category='warning',
                    title='Research Quality Not Translating',
                    description='Your high-quality research isn\'t outperforming. Consider if your research process needs adjustment.',
                    supporting_data=f'High quality: {hq_avg:.1f}% avg, Low quality: {lq_avg:.1f}% avg',
                    importance='high'
                ))
        
        return insights
    
    def _analyze_holding_patterns(self, outcomes) -> List[LearningInsight]:
        """Analyze holding period patterns"""
        insights = []
        
        short_holds = []  # < 90 days
        long_holds = []   # >= 90 days
        
        for o in outcomes:
            if o.exit_date and o.entry_date:
                days = (o.exit_date - o.entry_date).days
                if days < SHORT_HOLD_THRESHOLD_DAYS:
                    short_holds.append(float(o.realized_return_pct))
                else:
                    long_holds.append(float(o.realized_return_pct))
        
        if short_holds and long_holds:
            short_avg = sum(short_holds) / len(short_holds)
            long_avg = sum(long_holds) / len(long_holds)
            
            if long_avg > short_avg + 5:
                insights.append(LearningInsight(
                    category='winning_pattern',
                    title='Patience Pays Off',
                    description=f'Positions held 90+ days return {long_avg - short_avg:.1f}% more on average.',
                    supporting_data=f'Long holds: {long_avg:.1f}% avg ({len(long_holds)} trades), Short holds: {short_avg:.1f}% avg ({len(short_holds)} trades)',
                    importance='high'
                ))
            elif short_avg > long_avg + 5:
                insights.append(LearningInsight(
                    category='winning_pattern',
                    title='Quick Trades Working',
                    description=f'Your shorter-term trades (<90 days) are outperforming.',
                    supporting_data=f'Short holds: {short_avg:.1f}% avg, Long holds: {long_avg:.1f}% avg',
                    importance='medium'
                ))
        
        return insights
    
    def _analyze_confidence_calibration(self, outcomes, journals_by_company=None) -> List[LearningInsight]:
        """Analyze if confidence scores predict outcomes"""
        insights = []
        confidence_returns = []
        for o in outcomes:
            journal = (journals_by_company or {}).get(o.company_id)

            if journal and journal.confidence_score:
                confidence_returns.append({
                    'confidence': journal.confidence_score,
                    'return': float(o.realized_return_pct)
                })
        
        if len(confidence_returns) >= MIN_CONFIDENCE_RETURN_SAMPLES:
            high_conf = [cr for cr in confidence_returns if cr['confidence'] >= 8]
            low_conf = [cr for cr in confidence_returns if cr['confidence'] <= 5]
            
            if high_conf and low_conf:
                hc_avg = sum(cr['return'] for cr in high_conf) / len(high_conf)
                lc_avg = sum(cr['return'] for cr in low_conf) / len(low_conf)
                
                if lc_avg > hc_avg:
                    insights.append(LearningInsight(
                        category='warning',
                        title='Overconfidence Alert',
                        description='High confidence trades (8-10) are underperforming low confidence trades. Consider if you\'re overconfident in some picks.',
                        supporting_data=f'High confidence: {hc_avg:.1f}% avg, Low confidence: {lc_avg:.1f}% avg',
                        importance='high'
                    ))
                elif hc_avg > lc_avg + 10:
                    insights.append(LearningInsight(
                        category='edge',
                        title='Well Calibrated Confidence',
                        description='Your high-confidence picks significantly outperform. You\'re good at knowing when you have an edge.',
                        supporting_data=f'High confidence: {hc_avg:.1f}% avg, Low confidence: {lc_avg:.1f}% avg',
                        importance='medium'
                    ))
        
        return insights
    
    def _analyze_sector_patterns(self, outcomes) -> List[LearningInsight]:
        """Analyze sector performance patterns"""
        insights = []
        sector_returns = {}

        for o in outcomes:
            company = o.company  # Already eager-loaded in get_learning_insights
            if company and company.sector:
                sector_name = company.sector.display_name  # Use display_name for better readability
                if sector_name not in sector_returns:
                    sector_returns[sector_name] = []
                sector_returns[sector_name].append(float(o.realized_return_pct))
        
        if len(sector_returns) >= 2:
            sector_avgs = {
                sector: sum(returns) / len(returns)
                for sector, returns in sector_returns.items()
                if len(returns) >= 2
            }
            
            if sector_avgs:
                best_sector = max(sector_avgs, key=sector_avgs.get)
                worst_sector = min(sector_avgs, key=sector_avgs.get)
                
                if sector_avgs[best_sector] > 10:
                    insights.append(LearningInsight(
                        category='winning_pattern',
                        title=f'{best_sector} Is Your Sweet Spot',
                        description=f'You\'re averaging {sector_avgs[best_sector]:.1f}% returns in {best_sector}.',
                        supporting_data=f'{len(sector_returns[best_sector])} trades',
                        importance='medium'
                    ))
                
                if sector_avgs[worst_sector] < -5:
                    insights.append(LearningInsight(
                        category='warning',
                        title=f'Struggling in {worst_sector}',
                        description=f'Your {worst_sector} trades average {sector_avgs[worst_sector]:.1f}%. Consider avoiding or researching more carefully.',
                        supporting_data=f'{len(sector_returns[worst_sector])} trades',
                        importance='medium'
                    ))
        
        return insights


# ============================================================
# Convenience Functions (cached to avoid redundant computation)
# ============================================================

@cache.memoize(timeout=3600)  # 1 hour — correlation data changes only on trade close
def get_correlation_data(user_id: int) -> CorrelationData:
    """Get research quality to returns correlation data"""
    service = PortfolioIntelligenceService(user_id)
    return service.get_correlation_data()


@cache.memoize(timeout=300)  # 5 min — checkpoint status changes infrequently
def get_upcoming_checkpoints(user_id: int, days_ahead: int = 30) -> Dict[str, List[CheckpointReminder]]:
    """Get upcoming and overdue checkpoints"""
    service = PortfolioIntelligenceService(user_id)
    return service.get_upcoming_checkpoints(days_ahead)


@cache.memoize(timeout=300)  # 5 min — position data changes with price refreshes
def get_thesis_reality_check(user_id: int) -> List[ThesisReality]:
    """Get thesis vs reality comparison for active positions"""
    service = PortfolioIntelligenceService(user_id)
    return service.get_thesis_reality_check()


@cache.memoize(timeout=1800)  # 30 min — trade history doesn't change frequently
def get_learning_insights(user_id: int) -> List[LearningInsight]:
    """Get personalized learning insights"""
    service = PortfolioIntelligenceService(user_id)
    return service.get_learning_insights()