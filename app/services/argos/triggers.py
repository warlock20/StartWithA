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
Argos Pre-Compute Triggers

Determines WHEN and WHAT to pre-compute when data events occur.
This is the "relevance check" step in the algorithm.

Data Event → is_relevant() → compute_insight() → store in ArgosInsightBase
"""

from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

from .config import (
    THRESHOLDS,
    EVENT_RELEVANCE,
    ConfidenceLevel,
    InsightCategory,
)
from .insights import PreComputedInsight


class PreComputeTrigger:
    """
    Handles pre-compute decisions for data events.

    Usage:
        trigger = PreComputeTrigger()

        # When mistake is logged
        if trigger.is_relevant('mistake_logged', mistake_data):
            insight = trigger.compute_insight('mistake_logged', mistake_data)
            # Store insight in DB
    """

    # =========================================================================
    # Main Entry Point
    # =========================================================================

    def is_relevant(self, event_type: str, data: Dict[str, Any]) -> bool:
        """
        Determine if this event warrants pre-computing an insight.

        Args:
            event_type: One of 'mistake_logged', 'trade_closed_loss', etc.
            data: Event-specific data dictionary

        Returns:
            True if we should pre-compute, False otherwise
        """
        if event_type not in EVENT_RELEVANCE:
            return False

        config = EVENT_RELEVANCE[event_type]

        # Always compute for high-priority events
        if config.get('always_compute', False):
            return True

        # Event-specific relevance checks
        check_method = getattr(self, f'_check_{event_type}', None)
        if check_method:
            return check_method(data)

        return False

    def compute_insight(
        self,
        event_type: str,
        data: Dict[str, Any]
    ) -> Optional[PreComputedInsight]:
        """
        Compute a pre-computed insight from event data.

        Args:
            event_type: Type of event
            data: Event-specific data

        Returns:
            PreComputedInsight ready to store, or None if computation fails
        """
        compute_method = getattr(self, f'_compute_{event_type}', None)
        if compute_method:
            return compute_method(data)
        return None

    # =========================================================================
    # Relevance Checks (per event type)
    # =========================================================================

    def _check_mistake_logged(self, data: Dict[str, Any]) -> bool:
        """Mistakes are always relevant."""
        # TODO: Discuss - any conditions where mistakes aren't relevant?
        # - Too old?
        # - Missing required fields?
        return True

    def _check_trade_closed_loss(self, data: Dict[str, Any]) -> bool:
        """
        Loss trades are relevant if loss exceeds threshold.

        Required data keys:
            - return_pct: float (negative for losses)
        """
        return_pct = data.get('return_pct', 0)
        threshold = THRESHOLDS['significant_loss_percent']

        # TODO: Discuss - other conditions?
        # - Holding period too short? (might be stop-loss, not mistake)
        # - Position size too small? (not material)

        return return_pct <= threshold

    def _check_trade_closed_profit(self, data: Dict[str, Any]) -> bool:
        """
        Profit trades are rarely insight-worthy.

        TODO: Discuss - when IS a profitable trade worth storing?
        - Exceptional return (>100%)?
        - Had thesis that can be learned from?
        """
        # For now, don't pre-compute profitable trades
        return False

    def _check_research_completed(self, data: Dict[str, Any]) -> bool:
        """
        Completed research is relevant if it has outcome data.

        Required data keys:
            - has_outcome: bool
            - outcome_return_pct: float (optional)
        """
        # TODO: Discuss - what counts as "has outcome"?
        # - Linked to a closed trade?
        # - User marked outcome manually?
        # - Time-based (research > 1 year old)?

        return data.get('has_outcome', False)

    def _check_thesis_updated(self, data: Dict[str, Any]) -> bool:
        """
        Thesis updates are relevant if significant.

        TODO: Discuss - what makes a thesis update "significant"?
        - Checkpoint with violated thesis?
        - Major changes to key assumptions?
        """
        # For now, don't pre-compute thesis updates
        return False

    # =========================================================================
    # Compute Methods (per event type)
    # =========================================================================

    def _compute_mistake_logged(self, data: Dict[str, Any]) -> PreComputedInsight:
        """
        Compute insight from a logged mistake.

        Required data keys:
            - id: int
            - user_id: int
            - title: str
            - description: str
            - sector: str (optional)
            - tags: List[str] (optional)
            - company_id: int (optional)
            - severity: str (optional)
        """
        # Extract keywords from title and description
        keywords = self._extract_keywords(
            data.get('title', ''),
            data.get('description', '')
        )

        # Build summary
        summary = self._build_summary_mistake(data)

        return PreComputedInsight(
            user_id=data['user_id'],
            source_type='mistake_log',
            source_id=data['id'],
            sector=data.get('sector'),
            tags=data.get('tags', []),
            company_ids=[data['company_id']] if data.get('company_id') else [],
            relevance_keywords=keywords,
            summary=summary,
            confidence=ConfidenceLevel.HIGH,
            severity=data.get('severity', 'medium'),
        )

    def _compute_trade_closed_loss(self, data: Dict[str, Any]) -> PreComputedInsight:
        """
        Compute insight from a significant loss trade.

        Required data keys:
            - id: int (transaction id)
            - user_id: int
            - company_id: int
            - company_name: str
            - sector: str
            - return_pct: float
            - notes: str (optional)
        """
        return_pct = data.get('return_pct', 0)
        severe_threshold = THRESHOLDS['severe_loss_percent']

        # Determine confidence based on severity
        confidence = (
            ConfidenceLevel.HIGH if return_pct <= severe_threshold
            else ConfidenceLevel.MEDIUM
        )

        # Extract keywords from notes
        keywords = self._extract_keywords(data.get('notes', ''))

        # Build summary
        summary = self._build_summary_loss(data)

        return PreComputedInsight(
            user_id=data['user_id'],
            source_type='trade_loss',
            source_id=data['id'],
            sector=data.get('sector'),
            tags=[],  # TODO: Extract tags from trade context
            company_ids=[data['company_id']],
            relevance_keywords=keywords,
            summary=summary,
            confidence=confidence,
            severity='high' if return_pct <= severe_threshold else 'medium',
        )

    def _compute_research_completed(self, data: Dict[str, Any]) -> PreComputedInsight:
        """
        Compute insight from completed research with outcome.

        Required data keys:
            - id: int (project id)
            - user_id: int
            - company_id: int
            - sector: str
            - outcome_return_pct: float
            - thesis_summary: str (optional)
        """
        # TODO: Implement when research outcome tracking is mature
        pass

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _extract_keywords(self, *texts: str) -> List[str]:
        """
        Extract relevance keywords from text.

        TODO: Discuss - should this use:
        - Simple word extraction?
        - TF-IDF?
        - LLM extraction?
        - Predefined keyword list matching?
        """
        keywords = []
        combined = ' '.join(texts).lower()

        # For now, simple approach: extract known important terms
        # TODO: Make this smarter
        important_terms = [
            'management', 'accounting', 'fraud', 'debt', 'competition',
            'margin', 'growth', 'valuation', 'moat', 'cycle', 'regulation',
            'inventory', 'receivables', 'cash', 'acquisition', 'dilution',
        ]

        for term in important_terms:
            if term in combined:
                keywords.append(term)

        return keywords

    def _build_summary_mistake(self, data: Dict[str, Any]) -> str:
        """Build a brief summary for a mistake insight."""
        title = data.get('title', 'Unknown mistake')
        sector = data.get('sector', '')

        if sector:
            return f"Mistake in {sector}: {title}"
        return f"Mistake: {title}"

    def _build_summary_loss(self, data: Dict[str, Any]) -> str:
        """Build a brief summary for a loss trade insight."""
        company = data.get('company_name', 'Unknown')
        return_pct = data.get('return_pct', 0)

        return f"Loss on {company}: {return_pct:.1f}%"

    # =========================================================================
    # Batch Processing (for initial population)
    # =========================================================================

    def compute_all_for_user(self, user_id: int) -> List[PreComputedInsight]:
        """
        Compute all insights for a user (initial setup or refresh).

        TODO: Implement - queries all relevant data and computes insights.
        """
        pass
