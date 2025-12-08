"""
Research Journal Intelligence Service

This service provides AI-powered features for the research journal:
- Automatic entry analysis and tagging
- Thesis contradiction detection
- Related entries identification
- Insight pattern recognition
"""

from typing import Dict, List, Optional, Any, Tuple
import json
from datetime import datetime, timedelta
from app import db
from app.models import JournalEntry, ThesisEvolution, Company, User
from app.ai.services.prompt_service import get_research_journal_prompt
from app.utils.time_utils import now_utc
import logging
import google.generativeai as genai
from flask import current_app
import os

logger = logging.getLogger(__name__)

class ResearchJournalIntelligence:
    """AI-powered research journal intelligence features"""

    def __init__(self):
        self.setup_gemini()

    def setup_gemini(self):
        """Initialize Gemini AI"""
        try:
            api_key = os.getenv('GEMINI_API_KEY')
            if api_key:
                genai.configure(api_key=api_key)
                self.model = genai.GenerativeModel('gemini-pro')
                logger.info("Gemini AI initialized successfully")
            else:
                logger.warning("GEMINI_API_KEY not found in environment")
                self.model = None
        except Exception as e:
            logger.error(f"Failed to initialize Gemini AI: {e}")
            self.model = None

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
            if not self.model:
                logger.warning("Gemini AI not available for entry analysis")
                return self._fallback_entry_analysis(entry)

            # Prepare user context
            if not user_context:
                user_context = self._build_user_context(entry.user_id, limit=10)

            # Get the prompt
            prompt = get_research_journal_prompt('entry_analysis',
                entry_title=entry.title or "Untitled Entry",
                entry_type=entry.entry_type,
                entry_content=entry.content,
                company_name=entry.company.name if entry.company else "General Market",
                ticker_symbol=entry.company.ticker_symbol if entry.company else "N/A",
                existing_tags=', '.join(entry.tags) if entry.tags else "None",
                user_journal_context=user_context['summary']
            )

            # Generate analysis
            response = self.model.generate_content(prompt)

            # Parse JSON response
            try:
                analysis_result = json.loads(response.text)

                # Validate and enhance the result
                analysis_result = self._validate_analysis_result(analysis_result, entry)

                logger.info(f"Successfully analyzed entry {entry.id}")
                return analysis_result

            except json.JSONDecodeError:
                logger.error(f"Failed to parse AI response as JSON: {response.text[:200]}...")
                return self._fallback_entry_analysis(entry)

        except Exception as e:
            logger.error(f"Error analyzing journal entry {entry.id}: {e}")
            return self._fallback_entry_analysis(entry)

    def detect_thesis_contradictions(self, entry: JournalEntry, company_id: int) -> Dict[str, Any]:
        """
        Check if a new journal entry contradicts the existing thesis for a company

        Args:
            entry: New journal entry to check
            company_id: Company ID to check thesis for

        Returns:
            Dictionary with contradiction analysis
        """
        try:
            if not self.model:
                logger.warning("Gemini AI not available for contradiction detection")
                return self._fallback_contradiction_detection()

            # Get current thesis
            current_thesis = ThesisEvolution.query.filter_by(
                user_id=entry.user_id,
                company_id=company_id,
                is_current=True
            ).first()

            if not current_thesis:
                logger.info(f"No current thesis found for company {company_id}")
                return {"contradiction_detected": False, "reason": "No thesis to compare against"}

            # Get recent thesis updates for context
            recent_updates = ThesisEvolution.query.filter_by(
                user_id=entry.user_id,
                company_id=company_id
            ).filter(
                ThesisEvolution.created_at >= now_utc() - timedelta(days=90)
            ).order_by(ThesisEvolution.created_at.desc()).limit(3).all()

            recent_thesis_text = "\n".join([
                f"Version {t.version} ({t.created_at.strftime('%Y-%m-%d')}): {t.change_summary or 'No summary'}"
                for t in recent_updates
            ])

            # Get the prompt
            prompt = get_research_journal_prompt('thesis_contradiction_detection',
                entry_title=entry.title or "Untitled Entry",
                entry_content=entry.content,
                entry_type=entry.entry_type,
                company_name=entry.company.name if entry.company else "Unknown",
                current_thesis=current_thesis.thesis,
                conviction_level=current_thesis.conviction_level or 5,
                recent_thesis_updates=recent_thesis_text
            )

            # Generate analysis
            response = self.model.generate_content(prompt)

            # Parse JSON response
            try:
                contradiction_result = json.loads(response.text)

                # Validate result
                if 'contradiction_detected' not in contradiction_result:
                    contradiction_result['contradiction_detected'] = False

                logger.info(f"Successfully checked thesis contradictions for entry {entry.id}")
                return contradiction_result

            except json.JSONDecodeError:
                logger.error(f"Failed to parse contradiction detection response: {response.text[:200]}...")
                return self._fallback_contradiction_detection()

        except Exception as e:
            logger.error(f"Error detecting thesis contradictions for entry {entry.id}: {e}")
            return self._fallback_contradiction_detection()

    def find_related_entries(self, entry: JournalEntry, limit: int = 5) -> Dict[str, Any]:
        """
        Find journal entries related to the given entry

        Args:
            entry: Entry to find relations for
            limit: Maximum number of related entries to return

        Returns:
            Dictionary with related entries and analysis
        """
        try:
            if not self.model:
                logger.warning("Gemini AI not available for related entries finding")
                return self._fallback_related_entries(entry, limit)

            # Get historical entries for the user
            historical_entries = JournalEntry.query.filter(
                JournalEntry.user_id == entry.user_id,
                JournalEntry.id != entry.id  # Exclude current entry
            ).order_by(JournalEntry.created_at.desc()).limit(50).all()

            if not historical_entries:
                return {
                    "related_entries": [],
                    "pattern_detected": "No historical entries to compare against",
                    "suggested_review_order": [],
                    "knowledge_gaps": []
                }

            # Format historical entries for AI analysis
            historical_entries_text = self._format_entries_for_ai(historical_entries)

            # Get the prompt
            prompt = get_research_journal_prompt('related_entries_finder',
                entry_title=entry.title or "Untitled Entry",
                entry_content=entry.content,
                company_name=entry.company.name if entry.company else "General Market",
                entry_tags=', '.join(entry.tags) if entry.tags else "None",
                historical_entries=historical_entries_text
            )

            # Generate analysis
            response = self.model.generate_content(prompt)

            # Parse JSON response
            try:
                related_result = json.loads(response.text)

                # Validate and limit results
                if 'related_entries' in related_result:
                    related_result['related_entries'] = related_result['related_entries'][:limit]

                logger.info(f"Successfully found related entries for entry {entry.id}")
                return related_result

            except json.JSONDecodeError:
                logger.error(f"Failed to parse related entries response: {response.text[:200]}...")
                return self._fallback_related_entries(entry, limit)

        except Exception as e:
            logger.error(f"Error finding related entries for entry {entry.id}: {e}")
            return self._fallback_related_entries(entry, limit)

    def _build_user_context(self, user_id: int, limit: int = 10) -> Dict[str, str]:
        """Build context about user's recent journal activity"""
        recent_entries = JournalEntry.query.filter_by(
            user_id=user_id
        ).order_by(JournalEntry.created_at.desc()).limit(limit).all()

        if not recent_entries:
            return {"summary": "No recent journal activity"}

        # Create summary of recent activity
        entry_summaries = []
        for entry in recent_entries:
            company_name = entry.company.name if entry.company else "General"
            summary = f"{entry.entry_type} about {company_name}: {entry.content[:100]}..."
            entry_summaries.append(summary)

        context_summary = f"Recent journal activity ({len(entry_summaries)} entries):\n" + \
                         "\n".join(f"- {summary}" for summary in entry_summaries)

        return {"summary": context_summary}

    def _format_entries_for_ai(self, entries: List[JournalEntry], max_length: int = 2000) -> str:
        """Format historical entries for AI analysis"""
        formatted_entries = []
        current_length = 0

        for entry in entries:
            company_name = entry.company.name if entry.company else "General"
            tags = ', '.join(entry.tags) if entry.tags else "No tags"

            entry_text = f"Entry #{entry.id} ({entry.created_at.strftime('%Y-%m-%d')}): " \
                        f"{entry.title or 'Untitled'} [{entry.entry_type}] - {company_name} - " \
                        f"Tags: {tags} - Content: {entry.content[:200]}..."

            if current_length + len(entry_text) > max_length:
                break

            formatted_entries.append(entry_text)
            current_length += len(entry_text)

        return "\n".join(formatted_entries)

    def _validate_analysis_result(self, result: Dict, entry: JournalEntry) -> Dict:
        """Validate and enhance analysis result"""
        # Ensure required fields exist
        if 'key_themes' not in result:
            result['key_themes'] = []
        if 'suggested_tags' not in result:
            result['suggested_tags'] = []
        if 'follow_up_questions' not in result:
            result['follow_up_questions'] = []

        # Add metadata
        result['analyzed_at'] = datetime.utcnow().isoformat()
        result['entry_id'] = entry.id
        result['ai_confidence'] = 0.8  # Default confidence score

        return result

    def _fallback_entry_analysis(self, entry: JournalEntry) -> Dict[str, Any]:
        """Fallback analysis when AI is not available"""
        # Simple rule-based analysis
        themes = []
        tags = []

        # Extract basic themes from content
        content_lower = entry.content.lower()

        # Common investment themes
        if any(word in content_lower for word in ['growth', 'revenue', 'sales']):
            themes.append('growth_analysis')
        if any(word in content_lower for word in ['risk', 'concern', 'worry']):
            themes.append('risk_assessment')
        if any(word in content_lower for word in ['management', 'ceo', 'leadership']):
            themes.append('management_quality')
        if any(word in content_lower for word in ['competition', 'competitive', 'moat']):
            themes.append('competitive_dynamics')

        # Generate basic tags based on content
        if entry.company:
            tags.append(f"company_{entry.company.ticker_symbol.lower()}")
        tags.append(entry.entry_type)

        return {
            'key_themes': themes,
            'key_insights': [],
            'suggested_tags': tags,
            'potential_connections': [],
            'follow_up_questions': [],
            'thesis_implications': 'AI analysis not available - manual review recommended',
            'knowledge_category': 'requires_review',
            'analyzed_at': datetime.utcnow().isoformat(),
            'entry_id': entry.id,
            'ai_confidence': 0.3,
            'fallback_used': True
        }

    def _fallback_contradiction_detection(self) -> Dict[str, Any]:
        """Fallback contradiction detection when AI is not available"""
        return {
            'contradiction_detected': False,
            'contradiction_severity': 'unknown',
            'reason': 'AI analysis not available - manual review recommended',
            'fallback_used': True
        }

    def _fallback_related_entries(self, entry: JournalEntry, limit: int) -> Dict[str, Any]:
        """Fallback related entries finding when AI is not available"""
        # Simple rule-based matching
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


# Global service instance
research_journal_intelligence = ResearchJournalIntelligence()


# Convenience functions for easy import
def analyze_journal_entry(entry: JournalEntry, user_context: Dict = None) -> Dict[str, Any]:
    """Analyze a journal entry for themes, insights, and connections"""
    return research_journal_intelligence.analyze_journal_entry(entry, user_context)


def detect_thesis_contradictions(entry: JournalEntry, company_id: int) -> Dict[str, Any]:
    """Check for thesis contradictions in a journal entry"""
    return research_journal_intelligence.detect_thesis_contradictions(entry, company_id)


def find_related_entries(entry: JournalEntry, limit: int = 5) -> Dict[str, Any]:
    """Find entries related to the given entry"""
    return research_journal_intelligence.find_related_entries(entry, limit)


# Helper function for prompt service integration
def get_research_journal_prompt(prompt_name: str, **kwargs) -> str:
    """Get a research journal prompt with variables"""
    from app.ai.services.prompt_service import prompt_service
    return prompt_service.get_prompt('research_journal', prompt_name, **kwargs)