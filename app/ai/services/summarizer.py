"""
Summarization Service

Handles AI-powered text summarization for sector research.
Uses PromptService for consistent, maintainable prompt management.
"""

import logging
import re
from typing import Dict, List, Optional

from ..providers.base import AIProvider
from ..providers.gemini import GeminiProvider
from .prompt_service import get_sector_research_prompt


logger = logging.getLogger(__name__)


class SummarizationService:
    """Service for generating AI-powered summaries of sector research"""

    def __init__(self, provider: Optional[AIProvider] = None, model: str = "gemini-2.5-flash"):
        """
        Initialize summarization service.

        Args:
            provider: AI provider to use (defaults to GeminiProvider)
            model: Model name to use (default: gemini-2.5-flash)
                   Options: gemini-2.5-flash, gemini-2.5-pro, gemini-2.0-flash
        """
        self.provider = provider or GeminiProvider(model=model)
        self.model = model

    def generate_sector_summary(
        self,
        sector_name: str,
        documentation: str = "",
        canvas_notes: Optional[List[Dict]] = None,
        snippets: Optional[List[Dict]] = None,
        sources: Optional[List[Dict]] = None,
        bullet_count: int = 7,
        focus: str = "balanced",
        temperature: float = 0.7
    ) -> Dict:
        """
        Generate AI summary of sector research.

        Args:
            sector_name: Name of the sector
            documentation: Documentation content
            canvas_notes: List of canvas notes
            snippets: List of research snippets
            sources: List of sources
            bullet_count: Number of bullet points (default: 7)
            focus: Focus area - "balanced", "insights", "risks", "opportunities"
            temperature: AI temperature (0-1, lower = more deterministic)

        Returns:
            Dict with:
                - success: bool
                - summary: str (generated summary text)
                - bullet_points: List[str] (extracted bullet points)
                - error: str (if failed)
                - token_count: int (estimated tokens used)
        """
        if not self.provider.is_available():
            return {
                'success': False,
                'error': 'AI provider is not available. Please check API key configuration.',
                'summary': '',
                'bullet_points': [],
                'token_count': 0
            }

        try:
            # Prepare research content
            research_content = self._prepare_research_content(
                documentation=documentation,
                canvas_notes=canvas_notes or [],
                snippets=snippets or [],
                sources=sources or []
            )

            # Prepare focus guideline based on focus parameter
            focus_guidelines = {
                "insights": "- Prioritize actionable investment insights and strategic implications",
                "risks": "- Focus heavily on risks, challenges, and potential red flags",
                "opportunities": "- Emphasize growth opportunities and positive catalysts",
                "balanced": ""  # No additional guideline for balanced
            }
            focus_guideline = focus_guidelines.get(focus, "")

            # Get formatted prompt from PromptService (YAML)
            prompt = get_sector_research_prompt(
                'section_summaries',
                sector_name=sector_name,
                bullet_count=bullet_count,
                research_content=research_content,
                focus_guideline=focus_guideline
            )

            # Estimate token count
            token_count = self.provider.count_tokens(prompt)
            logger.info(f"Generating sector summary for '{sector_name}' (~{token_count} tokens)")

            # Generate summary
            summary_text = self.provider.generate_text(
                prompt=prompt,
                temperature=temperature,
                max_tokens=1000  # Reasonable limit for bullet points
            )

            # Extract bullet points
            bullet_points = self._extract_bullet_points(summary_text)

            return {
                'success': True,
                'summary': summary_text.strip(),
                'bullet_points': bullet_points,
                'token_count': token_count
            }

        except Exception as e:
            logger.error(f"Error generating sector summary: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'summary': '',
                'bullet_points': [],
                'token_count': 0
            }

    def _prepare_research_content(
        self,
        documentation: str,
        canvas_notes: List[Dict],
        snippets: List[Dict],
        sources: List[Dict]
    ) -> str:
        """
        Prepare research content for prompt.

        Args:
            documentation: Documentation content
            canvas_notes: List of canvas notes
            snippets: List of research snippets
            sources: List of sources

        Returns:
            Formatted research content string
        """
        research_parts = []

        # Add documentation if available
        if documentation and documentation.strip():
            clean_doc = documentation[:3000]  # Limit length
            if clean_doc.strip():
                research_parts.append(f"## Documentation\n\n{clean_doc}")

        # Add canvas notes
        if canvas_notes:
            notes_text = "\n\n".join([
                f"**{note.get('title', 'Untitled')}**\n{note.get('content', '')[:500]}"
                for note in canvas_notes[:15]  # Limit to 15 notes
            ])
            if notes_text.strip():
                research_parts.append(f"## Research Notes\n\n{notes_text}")

        # Add snippets
        if snippets:
            snippets_text = "\n\n".join([
                f"**{snippet.get('category', 'other').replace('_', ' ').title()}**: {snippet.get('content', '')[:300]}"
                for snippet in snippets[:10]  # Limit to 10 snippets
            ])
            if snippets_text.strip():
                research_parts.append(f"## Key Snippets\n\n{snippets_text}")

        # Add sources context
        if sources:
            sources_text = "\n".join([
                f"- {source.get('title', 'Untitled source')}"
                for source in sources[:10]  # Limit to 10 sources
            ])
            if sources_text.strip():
                research_parts.append(f"## Research Sources\n\n{sources_text}")

        # Combine all research content
        research_content = "\n\n---\n\n".join(research_parts) if research_parts else "No research data available yet."

        return research_content[:8000]  # Limit total size

    def _extract_bullet_points(self, text: str) -> List[str]:
        """
        Extract bullet points from generated text.

        Args:
            text: Generated summary text

        Returns:
            List of bullet point strings (cleaned)
        """
        # Find lines starting with bullet markers
        bullet_pattern = r'^[\s]*[•\-\*]\s+(.+)$'
        lines = text.split('\n')

        bullet_points = []
        for line in lines:
            match = re.match(bullet_pattern, line.strip())
            if match:
                bullet_points.append(match.group(1).strip())

        return bullet_points

    def format_as_html(self, bullet_points: List[str]) -> str:
        """
        Format bullet points as HTML for Quill editor.

        Args:
            bullet_points: List of bullet point strings

        Returns:
            HTML formatted bullet list
        """
        if not bullet_points:
            return ""

        html_items = [f"<li>{point}</li>" for point in bullet_points]
        return f"<ul>{''.join(html_items)}</ul>"

    def format_as_markdown(self, bullet_points: List[str]) -> str:
        """
        Format bullet points as markdown.

        Args:
            bullet_points: List of bullet point strings

        Returns:
            Markdown formatted bullet list
        """
        if not bullet_points:
            return ""

        return '\n'.join([f"• {point}" for point in bullet_points])
