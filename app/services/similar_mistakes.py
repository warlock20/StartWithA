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
Similar Past Mistakes Service

Uses embeddings to find similar past investment decisions and show
their outcomes, helping users learn from their own history.

Features:
- Embed and store past decisions
- Find similar past decisions when making new ones
- Analyze patterns in past mistakes
- Surface relevant lessons at decision time

Usage:
    from app.services.similar_mistakes import SimilarMistakesService
    
    service = SimilarMistakesService(user_id=123)
    
    # When user is making a new decision
    similar = service.find_similar_decisions(
        thesis="I believe NVDA will grow because AI demand...",
        company_id=456
    )
    
    for decision in similar:
        print(f"Similar: {decision['ticker']} - Outcome: {decision['return_pct']}%")
"""

import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

from app.models import (
    DecisionJournal, Company, PortfolioPosition
)
from app.models.ai_intelligence import ResearchOutcome
# Use the unified AI embedding service
from app.services.ai.embedding_service import get_embedding_service, embed as get_embedding
from app.services.config_service import get_config

logger = logging.getLogger(__name__)


@dataclass
class SimilarDecision:
    """A similar past decision found via embedding search"""
    decision_id: int
    company_id: int
    ticker: str
    company_name: str
    sector: Optional[str]
    
    # Similarity
    similarity_score: float  # 0-1
    
    # Original decision
    decision_date: datetime
    thesis_snippet: str
    confidence_score: Optional[int]
    expected_return: Optional[float]
    
    # Outcome (if available)
    has_outcome: bool = False
    actual_return_pct: Optional[float] = None
    holding_days: Optional[int] = None
    outcome_category: Optional[str] = None  # 'big_win', 'win', 'loss', 'big_loss'
    
    # Context
    was_researched: bool = False
    lessons_learned: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'decision_id': self.decision_id,
            'company_id': self.company_id,
            'ticker': self.ticker,
            'company_name': self.company_name,
            'sector': self.sector,
            'similarity_score': round(self.similarity_score, 3),
            'decision_date': self.decision_date.isoformat() if self.decision_date else None,
            'thesis_snippet': self.thesis_snippet,
            'confidence_score': self.confidence_score,
            'expected_return': self.expected_return,
            'has_outcome': self.has_outcome,
            'actual_return_pct': round(self.actual_return_pct, 2) if self.actual_return_pct else None,
            'holding_days': self.holding_days,
            'outcome_category': self.outcome_category,
            'was_researched': self.was_researched,
            'lessons_learned': self.lessons_learned,
        }


@dataclass
class PatternInsight:
    """An insight derived from patterns in similar past decisions"""
    pattern_type: str  # 'repeated_mistake', 'success_pattern', 'sector_bias', etc.
    title: str
    message: str
    severity: str  # 'high', 'medium', 'low', 'info'
    supporting_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'pattern_type': self.pattern_type,
            'title': self.title,
            'message': self.message,
            'severity': self.severity,
            'supporting_data': self.supporting_data,
        }


class SimilarMistakesService:
    """
    Service for finding and learning from similar past decisions.
    
    Uses vector embeddings to semantically match current decisions
    with past ones, then analyzes outcomes to surface relevant lessons.
    """

    def __init__(self, user_id: int):
        self.user_id = user_id
        self._embedding_service = get_embedding_service()
        self._decision_embeddings_cache = None

    @property
    def MIN_SIMILARITY_THRESHOLD(self) -> float:
        """Get minimum similarity threshold from user config"""
        return get_config('similarity_threshold', self.user_id, 0.65)

    @property
    def HIGH_SIMILARITY_THRESHOLD(self) -> float:
        """Get high similarity threshold from user config"""
        return get_config('high_similarity_threshold', self.user_id, 0.80)

    @property
    def MAX_SIMILAR_RESULTS(self) -> int:
        """Get max results from user config"""
        return get_config('max_similar_results', self.user_id, 10)

    @property
    def OUTCOME_THRESHOLDS(self) -> Dict[str, float]:
        """Get outcome thresholds from user config"""
        return {
            'big_win': get_config('big_win_threshold_pct', self.user_id, 25.0),
            'win': get_config('win_threshold_pct', self.user_id, 5.0),
            'small_loss': get_config('small_loss_threshold_pct', self.user_id, -5.0),
            'loss': get_config('loss_threshold_pct', self.user_id, -15.0),
            # Below -15% is 'big_loss'
        }
    
    def find_similar_decisions(
        self,
        thesis: str,
        company_id: Optional[int] = None,
        sector: Optional[str] = None,
        exclude_company: bool = True,
        min_similarity: float = None,
        max_results: int = None
    ) -> List[SimilarDecision]:
        """
        Find similar past decisions based on thesis text.
        
        Args:
            thesis: Current investment thesis
            company_id: Current company (to optionally exclude)
            sector: Current sector (for filtering)
            exclude_company: Whether to exclude same company
            min_similarity: Minimum similarity threshold
            max_results: Maximum results to return
            
        Returns:
            List of SimilarDecision objects
        """
        if not thesis or len(thesis.strip()) < 20:
            return []
        
        min_similarity = min_similarity or self.MIN_SIMILARITY_THRESHOLD
        max_results = max_results or self.MAX_SIMILAR_RESULTS
        
        # Get embedding for current thesis
        query_embedding = get_embedding(thesis)
        if query_embedding is None:
            logger.warning("Failed to generate embedding for thesis")
            return []
        
        # Get all past decisions with embeddings
        past_decisions = self._get_past_decisions_with_embeddings(
            exclude_company_id=company_id if exclude_company else None
        )
        
        if not past_decisions:
            return []
        
        # Find similar
        similar_results = self._embedding_service.find_similar(
            query_embedding=query_embedding,
            candidate_embeddings=[(d['id'], d['embedding']) for d in past_decisions],
            top_k=max_results * 2,  # Get more, then filter
            min_similarity=min_similarity
        )
        
        # Build result objects with full context
        results = []
        for decision_id, similarity in similar_results:
            decision_data = next((d for d in past_decisions if d['id'] == decision_id), None)
            if decision_data:
                similar_decision = self._build_similar_decision(decision_data, similarity)
                if similar_decision:
                    results.append(similar_decision)
                    if len(results) >= max_results:
                        break
        
        return results
    
    def analyze_patterns(
        self,
        similar_decisions: List[SimilarDecision]
    ) -> List[PatternInsight]:
        """
        Analyze patterns in similar past decisions.
        
        Args:
            similar_decisions: List of similar decisions found
            
        Returns:
            List of pattern insights
        """
        if not similar_decisions:
            return []
        
        insights = []
        
        # Filter to decisions with outcomes
        with_outcomes = [d for d in similar_decisions if d.has_outcome]
        
        if not with_outcomes:
            return insights
        
        # Pattern 1: Repeated losses in similar situations
        losses = [d for d in with_outcomes if d.actual_return_pct and d.actual_return_pct < -5]
        if len(losses) >= 2:
            avg_loss = sum(d.actual_return_pct for d in losses) / len(losses)
            tickers = [d.ticker for d in losses[:3]]
            
            insights.append(PatternInsight(
                pattern_type='repeated_losses',
                title='Similar Theses Led to Losses',
                message=(
                    f'{len(losses)} similar past decisions resulted in losses '
                    f'(avg: {avg_loss:.1f}%). Tickers: {", ".join(tickers)}. '
                    f'Consider what made these theses wrong.'
                ),
                severity='high' if len(losses) >= 3 else 'medium',
                supporting_data={
                    'loss_count': len(losses),
                    'avg_loss': avg_loss,
                    'tickers': tickers
                }
            ))
        
        # Pattern 2: Success pattern
        wins = [d for d in with_outcomes if d.actual_return_pct and d.actual_return_pct > 10]
        if len(wins) >= 2:
            avg_win = sum(d.actual_return_pct for d in wins) / len(wins)
            tickers = [d.ticker for d in wins[:3]]
            
            insights.append(PatternInsight(
                pattern_type='success_pattern',
                title='Similar Theses Have Worked',
                message=(
                    f'{len(wins)} similar past decisions were successful '
                    f'(avg: +{avg_win:.1f}%). This type of thesis has worked for you before.'
                ),
                severity='info',
                supporting_data={
                    'win_count': len(wins),
                    'avg_win': avg_win,
                    'tickers': tickers
                }
            ))
        
        # Pattern 3: Overconfidence in similar situations
        high_conf_losses = [
            d for d in with_outcomes 
            if d.confidence_score and d.confidence_score >= 8 
            and d.actual_return_pct and d.actual_return_pct < -10
        ]
        if high_conf_losses:
            insights.append(PatternInsight(
                pattern_type='overconfidence_history',
                title='High Confidence Didn\'t Help',
                message=(
                    f'You had high confidence in {len(high_conf_losses)} similar situations '
                    f'that resulted in significant losses. Your confidence may not correlate '
                    f'with outcomes for this type of thesis.'
                ),
                severity='medium',
                supporting_data={
                    'count': len(high_conf_losses),
                    'tickers': [d.ticker for d in high_conf_losses[:3]]
                }
            ))
        
        # Pattern 4: Sector concentration in past similar decisions
        sectors = [d.sector for d in similar_decisions if d.sector]
        if sectors:
            from collections import Counter
            sector_counts = Counter(sectors)
            most_common_sector, count = sector_counts.most_common(1)[0]
            
            if count >= 3:
                sector_outcomes = [
                    d.actual_return_pct for d in with_outcomes 
                    if d.sector == most_common_sector and d.actual_return_pct
                ]
                avg_return = sum(sector_outcomes) / len(sector_outcomes) if sector_outcomes else 0
                
                insights.append(PatternInsight(
                    pattern_type='sector_pattern',
                    title=f'You Often Have Similar Theses in {most_common_sector}',
                    message=(
                        f'{count} of your similar past decisions were in {most_common_sector}. '
                        f'Average outcome: {avg_return:+.1f}%. Consider if this reflects conviction or bias.'
                    ),
                    severity='low',
                    supporting_data={
                        'sector': most_common_sector,
                        'count': count,
                        'avg_return': avg_return
                    }
                ))
        
        # Pattern 5: Research correlation
        researched = [d for d in with_outcomes if d.was_researched]
        not_researched = [d for d in with_outcomes if not d.was_researched]
        
        if researched and not_researched:
            researched_avg = sum(d.actual_return_pct for d in researched if d.actual_return_pct) / len(researched)
            not_researched_avg = sum(d.actual_return_pct for d in not_researched if d.actual_return_pct) / len(not_researched)
            
            if researched_avg > not_researched_avg + 5:
                insights.append(PatternInsight(
                    pattern_type='research_helps',
                    title='Research Made a Difference',
                    message=(
                        f'Similar decisions with research averaged {researched_avg:+.1f}% vs '
                        f'{not_researched_avg:+.1f}% without. Research helps with this type of thesis.'
                    ),
                    severity='info',
                    supporting_data={
                        'researched_avg': researched_avg,
                        'not_researched_avg': not_researched_avg,
                        'researched_count': len(researched),
                        'not_researched_count': len(not_researched)
                    }
                ))
        
        return insights
    
    def get_warnings_for_transaction(
        self,
        thesis: str,
        company_id: int,
        company: Any
    ) -> List[Dict[str, Any]]:
        """
        Get warnings based on similar past decisions.
        
        Used by IntelligenceEngine during transaction checks.
        
        Args:
            thesis: Investment thesis
            company_id: Company ID
            company: Company object
            
        Returns:
            List of warning dicts
        """
        warnings = []
        
        # Find similar past decisions
        similar = self.find_similar_decisions(
            thesis=thesis,
            company_id=company_id,
            max_results=5
        )
        
        if not similar:
            return warnings
        
        # Analyze patterns
        patterns = self.analyze_patterns(similar)
        
        # Convert high/medium severity patterns to warnings
        for pattern in patterns:
            if pattern.severity in ['high', 'medium']:
                warnings.append({
                    'code': f'similar_mistake_{pattern.pattern_type}',
                    'severity': pattern.severity,
                    'category': 'behavioral',
                    'title': pattern.title,
                    'message': pattern.message,
                    'data': {
                        'pattern_type': pattern.pattern_type,
                        'similar_decisions_count': len(similar),
                        **pattern.supporting_data
                    }
                })
        
        # Add general similar decisions warning if multiple losses
        decisions_with_outcomes = [d for d in similar if d.has_outcome]
        losses = [d for d in decisions_with_outcomes if d.actual_return_pct and d.actual_return_pct < 0]
        
        if len(losses) >= 2 and len(losses) / len(decisions_with_outcomes) > 0.5:
            # More than half of similar decisions were losses
            warnings.append({
                'code': 'similar_decisions_mostly_losses',
                'severity': 'high',
                'category': 'behavioral',
                'title': 'History Suggests Caution',
                'message': (
                    f'{len(losses)} of {len(decisions_with_outcomes)} similar past decisions '
                    f'resulted in losses. Review what went wrong before proceeding.'
                ),
                'data': {
                    'similar_decisions': [d.to_dict() for d in similar[:3]],
                    'loss_rate': len(losses) / len(decisions_with_outcomes)
                }
            })
        
        return warnings
    
    def _get_past_decisions_with_embeddings(
        self,
        exclude_company_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get past decisions with their embeddings"""
        
        # Query past BUY decisions with thesis
        query = DecisionJournal.query.filter(
            DecisionJournal.user_id == self.user_id,
            DecisionJournal.decision_type == 'BUY',
            DecisionJournal.is_portfolio_decision == True,
            DecisionJournal.investment_thesis.isnot(None),
            DecisionJournal.investment_thesis != ''
        )
        
        if exclude_company_id:
            query = query.filter(DecisionJournal.company_id != exclude_company_id)
        
        decisions = query.all()
        
        results = []
        for decision in decisions:
            # Get or compute embedding
            embedding = get_embedding(decision.investment_thesis_text)

            if embedding is not None:
                # Get company info
                company = Company.query.get(decision.company_id)

                # Get outcome if available
                outcome = self._get_decision_outcome(decision)
                
                # Check if researched
                was_researched = decision.linked_research_id is not None
                
                results.append({
                    'id': decision.id,
                    'embedding': embedding,
                    'company_id': decision.company_id,
                    'company': company,
                    'thesis': decision.investment_thesis_text,
                    'decision_date': decision.decision_date,
                    'confidence_score': decision.confidence_score,
                    'expected_return': decision.expected_return,
                    'was_researched': was_researched,
                    'outcome': outcome
                })
        
        return results
    
    def _get_decision_outcome(self, decision: DecisionJournal) -> Optional[Dict[str, Any]]:
        """Get outcome for a decision if position is closed or has history"""
        
        # Check if there's a ResearchOutcome record
        try:
            outcome = ResearchOutcome.query.filter_by(
                decision_journal_id=decision.id
            ).first()
            
            if outcome and outcome.realized_return_pct is not None:
                return {
                    'return_pct': float(outcome.realized_return_pct),
                    'holding_days': outcome.holding_days,
                    'category': outcome.outcome_category,
                    'lessons_learned': outcome.lessons_learned
                }
        except Exception:
            pass
        
        # Fallback: Check current position
        position = PortfolioPosition.query.filter_by(
            user_id=self.user_id,
            company_id=decision.company_id
        ).first()
        
        if position:
            if position.is_active and position.unrealized_gain_loss_pct:
                # Position still open - use unrealized
                return {
                    'return_pct': float(position.unrealized_gain_loss_pct),
                    'holding_days': position.days_held,
                    'category': self._categorize_return(float(position.unrealized_gain_loss_pct)),
                    'lessons_learned': None,
                    'is_unrealized': True
                }
        
        return None
    
    def _categorize_return(self, return_pct: float) -> str:
        """Categorize return into outcome bucket"""
        if return_pct >= self.OUTCOME_THRESHOLDS['big_win']:
            return 'big_win'
        elif return_pct >= self.OUTCOME_THRESHOLDS['win']:
            return 'win'
        elif return_pct >= self.OUTCOME_THRESHOLDS['small_loss']:
            return 'small_loss'
        elif return_pct >= self.OUTCOME_THRESHOLDS['loss']:
            return 'loss'
        else:
            return 'big_loss'
    
    def _build_similar_decision(
        self,
        decision_data: Dict[str, Any],
        similarity: float
    ) -> Optional[SimilarDecision]:
        """Build SimilarDecision object from data"""
        
        company = decision_data.get('company')
        if not company:
            return None
        
        outcome = decision_data.get('outcome')
        
        return SimilarDecision(
            decision_id=decision_data['id'],
            company_id=decision_data['company_id'],
            ticker=company.ticker_symbol,
            company_name=company.name,
            sector=company.sector.display_name if company.sector else None,
            similarity_score=similarity,
            decision_date=decision_data.get('decision_date'),
            thesis_snippet=decision_data['thesis'][:200] + '...' if len(decision_data['thesis']) > 200 else decision_data['thesis'],
            confidence_score=decision_data.get('confidence_score'),
            expected_return=decision_data.get('expected_return'),
            has_outcome=outcome is not None,
            actual_return_pct=outcome.get('return_pct') if outcome else None,
            holding_days=outcome.get('holding_days') if outcome else None,
            outcome_category=outcome.get('category') if outcome else None,
            was_researched=decision_data.get('was_researched', False),
            lessons_learned=outcome.get('lessons_learned') if outcome else None
        )
    
    def index_all_decisions(self) -> int:
        """
        Pre-compute and cache embeddings for all past decisions.
        
        Call this periodically or after bulk imports.
        
        Returns:
            Number of decisions indexed
        """
        decisions = DecisionJournal.query.filter(
            DecisionJournal.user_id == self.user_id,
            DecisionJournal.decision_type == 'BUY',
            DecisionJournal.is_portfolio_decision == True,
            DecisionJournal.investment_thesis.isnot(None)
        ).all()
        
        count = 0
        for decision in decisions:
            if decision.investment_thesis:
                embedding = get_embedding(decision.investment_thesis_text, use_cache=True)
                if embedding is not None:
                    count += 1
        
        logger.info(f"Indexed {count} decisions for user {self.user_id}")
        return count


# ═══════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def find_similar_past_decisions(
    user_id: int,
    thesis: str,
    company_id: Optional[int] = None,
    max_results: int = 5
) -> List[SimilarDecision]:
    """
    Find similar past decisions for a user.
    
    Convenience function for routes.
    """
    service = SimilarMistakesService(user_id)
    return service.find_similar_decisions(
        thesis=thesis,
        company_id=company_id,
        max_results=max_results
    )


def get_similar_mistakes_warnings(
    user_id: int,
    thesis: str,
    company_id: int,
    company: Any
) -> List[Dict[str, Any]]:
    """
    Get warnings based on similar past decisions.
    
    Convenience function for IntelligenceEngine.
    """
    service = SimilarMistakesService(user_id)
    return service.get_warnings_for_transaction(thesis, company_id, company)