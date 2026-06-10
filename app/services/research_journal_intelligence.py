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
Research Journal Intelligence Service

This service provides AI-powered features for the research journal:
- Automatic entry analysis and tagging
- Thesis contradiction detection
- Related entries identification
- Insight pattern recognition

"""

import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from app import db
from app.models import JournalEntry, ThesisEvolution, Company, User
from app.utils.time_utils import now_utc

# New imports from unified AI service
from app.services.ai import ai_service, AITaskType
from app.services.ai.prompt_service import get_research_journal_prompt

logger = logging.getLogger(__name__)


class ResearchJournalIntelligence:
    """AI-powered research journal intelligence features"""

    def __init__(self):
        """Initialize with the unified AI service"""
        self.ai = ai_service

    def analyze_journal_entry(self, entry: JournalEntry, user_context: Dict = None) -> Dict[str, Any]:
        """
        Analyze a journal entry to extract themes, insights, and suggest connections

        Args:
            entry: JournalEntry object to analyze
            user_context: Optional context about user's other entries

        Returns:
            Dictionary with analysis results
        """
        try:
            if not self.ai.is_available():
                logger.warning("AI service not available for entry analysis")
                return self._fallback_entry_analysis(entry)

            # Prepare user context
            if not user_context:
                user_context = self._build_user_context(entry.user_id, limit=10)

            # Get the prompt from prompt service
            prompt = get_research_journal_prompt(
                'entry_analysis',
                entry_title=entry.title or "Untitled Entry",
                entry_type=entry.entry_type or "general",
                entry_content=entry.content or "",
                company_name=entry.company.name if entry.company else "N/A",
                ticker_symbol=entry.company.ticker_symbol if entry.company else "N/A",
                existing_tags=self._format_tags(entry),
                user_journal_context=json.dumps(user_context, default=str)
            )

            # Use AI service for analysis
            result = self.ai.generate_json(prompt, task=AITaskType.JOURNAL_ANALYSIS)

            logger.info(f"Successfully analyzed journal entry {entry.id}")
            return result

        except Exception as e:
            logger.error(f"Error analyzing journal entry {entry.id}: {e}")
            return self._fallback_entry_analysis(entry)

    def detect_thesis_contradictions(self, entry: JournalEntry, company_id: int) -> Dict[str, Any]:
        """
        Check if a journal entry contains information that contradicts
        the existing thesis for a company.

        Args:
            entry: JournalEntry to check
            company_id: Company to check thesis for

        Returns:
            Dictionary with contradiction analysis
        """
        try:
            if not self.ai.is_available():
                return self._fallback_contradiction_check(entry, company_id)

            # Get existing thesis evolution for this company
            thesis_entries = ThesisEvolution.query.filter_by(
                user_id=entry.user_id,
                company_id=company_id
            ).order_by(ThesisEvolution.created_at.desc()).limit(5).all()

            if not thesis_entries:
                return {
                    'has_contradictions': False,
                    'message': 'No existing thesis found for comparison',
                    'contradictions': []
                }

            # Build thesis context
            thesis_context = []
            for te in thesis_entries:
                thesis_context.append({
                    'date': te.created_at.isoformat() if te.created_at else 'Unknown',
                    'thesis': te.current_thesis or '',
                    'key_assumptions': te.key_assumptions or '',
                    'confidence': te.confidence_level
                })

            # Get the prompt
            prompt = get_research_journal_prompt(
                'thesis_contradiction_detection',
                entry_content=entry.content or "",
                entry_date=entry.created_at.isoformat() if entry.created_at else "Unknown",
                thesis_history=json.dumps(thesis_context, default=str),
                company_name=entry.company.name if entry.company else "Unknown"
            )

            result = self.ai.generate_json(prompt, task=AITaskType.THESIS_ANALYSIS)

            logger.info(f"Contradiction check completed for entry {entry.id}")
            return result

        except Exception as e:
            logger.error(f"Error checking contradictions for entry {entry.id}: {e}")
            return self._fallback_contradiction_check(entry, company_id)

    def find_related_entries(self, entry: JournalEntry, limit: int = 5) -> Dict[str, Any]:
        """
        Find journal entries that are related to the given entry.

        Args:
            entry: JournalEntry to find relations for
            limit: Maximum number of related entries to return

        Returns:
            Dictionary with related entries and relationship explanations
        """
        try:
            if not self.ai.is_available():
                return self._fallback_find_related(entry, limit)

            # Get recent entries from the same user (excluding current)
            recent_entries = JournalEntry.query.filter(
                JournalEntry.user_id == entry.user_id,
                JournalEntry.id != entry.id
            ).order_by(JournalEntry.created_at.desc()).limit(20).all()

            if not recent_entries:
                return {
                    'related_entries': [],
                    'message': 'No other entries found for comparison'
                }

            # Build context for comparison
            entries_context = []
            for e in recent_entries:
                entries_context.append({
                    'id': e.id,
                    'title': e.title or 'Untitled',
                    'type': e.entry_type,
                    'content_preview': (e.content or '')[:300],
                    'company': e.company.name if e.company else None,
                    'created_at': e.created_at.isoformat() if e.created_at else None
                })

            prompt = get_research_journal_prompt(
                'related_entries_finder',
                current_entry_title=entry.title or "Untitled",
                current_entry_content=entry.content or "",
                current_entry_type=entry.entry_type or "general",
                candidate_entries=json.dumps(entries_context, default=str),
                max_results=limit
            )

            result = self.ai.generate_json(prompt, task=AITaskType.JOURNAL_ANALYSIS)

            logger.info(f"Found related entries for entry {entry.id}")
            return result

        except Exception as e:
            logger.error(f"Error finding related entries for {entry.id}: {e}")
            return self._fallback_find_related(entry, limit)

    def _build_user_context(self, user_id: int, limit: int = 10) -> Dict[str, Any]:
        """Build context from user's recent journal activity"""
        recent_entries = JournalEntry.query.filter_by(
            user_id=user_id
        ).order_by(JournalEntry.created_at.desc()).limit(limit).all()

        # Extract common themes and topics
        themes = []
        companies_mentioned = set()

        for entry in recent_entries:
            if entry.company:
                companies_mentioned.add(entry.company.name)
            if entry.ai_themes_extracted:
                themes.extend(entry.ai_themes_extracted)

        return {
            'recent_entry_count': len(recent_entries),
            'companies_researched': list(companies_mentioned)[:10],
            'common_themes': list(set(themes))[:10] if themes else [],
            'active_period': 'last_30_days'
        }

    def _format_tags(self, entry: JournalEntry) -> str:
        """Format entry tags as string"""
        if hasattr(entry, 'tags') and entry.tags:
            return ', '.join([t.name for t in entry.tags])
        return "None"

    # ============================================================
    # Fallback Methods (when AI is unavailable)
    # ============================================================

    def _fallback_entry_analysis(self, entry: JournalEntry) -> Dict[str, Any]:
        """Simple rule-based analysis when AI is not available"""
        content = entry.content or ""
        content_lower = content.lower()

        # Extract simple themes based on keywords
        themes = []
        if 'revenue' in content_lower or 'sales' in content_lower:
            themes.append('financial_metrics')
        if 'competitor' in content_lower or 'competition' in content_lower:
            themes.append('competitive_analysis')
        if 'risk' in content_lower or 'concern' in content_lower:
            themes.append('risk_assessment')
        if 'growth' in content_lower or 'expand' in content_lower:
            themes.append('growth_analysis')
        if 'management' in content_lower or 'ceo' in content_lower:
            themes.append('management_quality')

        # Suggest tags based on content
        suggested_tags = []
        if entry.company:
            suggested_tags.append(entry.company.ticker_symbol.lower())
        if themes:
            suggested_tags.extend(themes[:3])

        return {
            'key_themes': themes or ['general_research'],
            'key_insights': ['Manual review recommended - AI analysis not available'],
            'suggested_tags': suggested_tags,
            'potential_connections': [],
            'follow_up_questions': [],
            'thesis_implications': None,
            'knowledge_category': entry.entry_type or 'general',
            'fallback_used': True
        }

    def _fallback_contradiction_check(self, entry: JournalEntry, company_id: int) -> Dict[str, Any]:
        """Simple contradiction check when AI is not available"""
        return {
            'has_contradictions': False,
            'contradictions': [],
            'analysis_method': 'fallback',
            'message': 'AI analysis not available - manual review recommended',
            'fallback_used': True
        }

    def _fallback_find_related(self, entry: JournalEntry, limit: int) -> Dict[str, Any]:
        """Simple related entries finder when AI is not available"""
        related_entries = []

        # Find entries with same company
        if entry.company:
            company_entries = JournalEntry.query.filter(
                JournalEntry.user_id == entry.user_id,
                JournalEntry.company_id == entry.company_id,
                JournalEntry.id != entry.id
            ).order_by(JournalEntry.created_at.desc()).limit(limit).all()

            for related_entry in company_entries:
                related_entries.append({
                    'entry_id': related_entry.id,
                    'entry_title': related_entry.title or 'Untitled',
                    'relationship_type': 'same_company',
                    'relevance_score': 0.7,
                    'connection_explanation': f'Both entries about {entry.company.name}',
                    'key_insight_connection': 'Company-specific analysis'
                })

        return {
            'related_entries': related_entries,
            'pattern_detected': 'Simple rule-based matching used - AI analysis not available',
            'suggested_review_order': [r['entry_id'] for r in related_entries],
            'knowledge_gaps': [],
            'fallback_used': True
        }


# ============================================================
# Global Service Instance
# ============================================================

research_journal_intelligence = ResearchJournalIntelligence()


# ============================================================
# Convenience Functions
# ============================================================

def analyze_journal_entry(entry: JournalEntry, user_context: Dict = None) -> Dict[str, Any]:
    """Analyze a journal entry for themes, insights, and connections"""
    return research_journal_intelligence.analyze_journal_entry(entry, user_context)


def detect_thesis_contradictions(entry: JournalEntry, company_id: int) -> Dict[str, Any]:
    """Check for thesis contradictions in a journal entry"""
    return research_journal_intelligence.detect_thesis_contradictions(entry, company_id)


def find_related_entries(entry: JournalEntry, limit: int = 5) -> Dict[str, Any]:
    """Find entries related to the given entry"""
    return research_journal_intelligence.find_related_entries(entry, limit)
