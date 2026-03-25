"""
Research Data Service

Centralized service for extracting and aggregating data from research workflow.
Used by: Argos, Bias Check, Portfolio Analytics, AI features.

This service provides a clean API for accessing research data without
needing to know the underlying model structure.
"""

import json
import logging
from typing import Optional
from dataclasses import dataclass
from app.utils.blocknote_utils import blocknote_to_text

logger = logging.getLogger(__name__)


@dataclass
class FreeResearchItem:
    """A single free research question with its answer."""
    question_id: int
    question_text: str
    answer_text: str
    status: str  # 'exploring' or 'answered'
    step_index: int


@dataclass
class ChecklistItem:
    """A single checklist question with its answer."""
    item_id: int
    question_text: str
    answer_text: str
    satisfaction_status: str  # 'satisfied', 'neutral', 'concerned'
    checklist_name: str


@dataclass
class ThesisSummary:
    """Summary of the investment thesis and decision."""
    investment_thesis: Optional[str]
    green_flags: list[str]
    red_flags: list[str]
    decision: Optional[str]
    decision_confidence: Optional[int]
    decision_notes: Optional[str]


class ResearchDataService:
    """
    Extract and aggregate data from research workflow.

    Provides a unified API for accessing research data from:
    - Free research questions/answers
    - Checklist questions/answers
    - Step notes
    - Investment thesis and summary fields

    Usage:
        from app.services.research_data_service import ResearchDataService

        service = ResearchDataService()
        text = service.get_all_text(project)
        free_research = service.get_free_research_data(project)
    """

    # =========================================================================
    # Text Extraction Utilities
    # =========================================================================

    @staticmethod
    def extract_text_from_blocknote(content) -> str:
        """
        Extract plain text from BlockNote JSON content.

        Args:
            content: Either a JSON string, parsed list of blocks, or plain text

        Returns:
            Plain text string
        """
        if not content:
            return ""

        # Already plain text
        if isinstance(content, str):
            # Try to parse as JSON
            try:
                content = json.loads(content)
            except (json.JSONDecodeError, TypeError):
                # It's plain text, return as-is
                return content

        # Extract text from BlockNote blocks
        if isinstance(content, list):
            texts = []
            for block in content:
                if isinstance(block, dict):
                    # Handle nested content array
                    block_content = block.get('content', [])
                    if isinstance(block_content, list):
                        for item in block_content:
                            if isinstance(item, dict) and 'text' in item:
                                texts.append(item['text'])
                            elif isinstance(item, str):
                                texts.append(item)
                    elif isinstance(block_content, str):
                        texts.append(block_content)

                    # Handle children blocks (nested lists, etc.)
                    children = block.get('children', [])
                    if children:
                        child_text = ResearchDataService.extract_text_from_blocknote(children)
                        if child_text:
                            texts.append(child_text)

            return ' '.join(filter(None, texts))

        return str(content) if content else ""

    # =========================================================================
    # Free Research Data
    # =========================================================================

    @staticmethod
    def get_free_research_data(project) -> list[FreeResearchItem]:
        """
        Get all free research questions and answers for a project.

        Args:
            project: ResearchProject instance

        Returns:
            List of FreeResearchItem dataclasses
        """
        from app.models import FreeResearchQuestion

        items = []
        questions = FreeResearchQuestion.query.filter_by(
            project_id=project.id
        ).order_by(
            FreeResearchQuestion.step_index,
            FreeResearchQuestion.order_index
        ).all()

        for q in questions:
            answer_text = ResearchDataService.extract_text_from_blocknote(q.answer_content)
            items.append(FreeResearchItem(
                question_id=q.id,
                question_text=q.question_text or "",
                answer_text=answer_text,
                status=q.status or "exploring",
                step_index=q.step_index
            ))

        return items

    @staticmethod
    def get_free_research_text(project) -> list[str]:
        """
        Get free research data as text strings.

        Args:
            project: ResearchProject instance

        Returns:
            List of text strings (question + answer pairs)
        """
        texts = []
        items = ResearchDataService.get_free_research_data(project)

        for item in items:
            if item.question_text:
                texts.append(f"Research Question: {item.question_text}")
            if item.answer_text:
                texts.append(f"Research Finding: {item.answer_text}")

        return texts

    # =========================================================================
    # Checklist Data
    # =========================================================================

    @staticmethod
    def get_checklist_data(project) -> list[ChecklistItem]:
        """
        Get all checklist answers for a project.

        Args:
            project: ResearchProject instance

        Returns:
            List of ChecklistItem dataclasses
        """
        from app.models import ChecklistAnalysis, ChecklistAnswer

        items = []

        # Get all checklist analyses for this project's company and user
        analyses = ChecklistAnalysis.query.filter_by(
            user_id=project.user_id,
            company_id=project.company_id
        ).all()

        for analysis in analyses:
            checklist_name = analysis.checklist.name if analysis.checklist else "Unknown Checklist"

            # Get all answers for this analysis
            answers = ChecklistAnswer.query.filter_by(
                checklist_analysis_id=analysis.id
            ).all()

            for answer in answers:
                question_text = ""
                if answer.item:
                    question_text = answer.item.text or ""

                answer_text = ResearchDataService.extract_text_from_blocknote(answer.answer_text)

                items.append(ChecklistItem(
                    item_id=answer.id,
                    question_text=question_text,
                    answer_text=answer_text,
                    satisfaction_status=answer.satisfaction_status or "neutral",
                    checklist_name=checklist_name
                ))

        return items

    @staticmethod
    def get_checklist_text(project) -> list[str]:
        """
        Get checklist data as text strings.

        Args:
            project: ResearchProject instance

        Returns:
            List of text strings (question + answer pairs)
        """
        texts = []
        items = ResearchDataService.get_checklist_data(project)

        for item in items:
            if item.question_text:
                texts.append(f"Checklist Question: {item.question_text}")
            if item.answer_text:
                texts.append(f"Answer: {item.answer_text}")

        # Also get conclusions from analyses
        from app.models import ChecklistAnalysis
        analyses = ChecklistAnalysis.query.filter_by(
            user_id=project.user_id,
            company_id=project.company_id
        ).all()

        for analysis in analyses:
            if analysis.conclusion:
                checklist_name = analysis.checklist.name if analysis.checklist else "Checklist"
                texts.append(f"{checklist_name} Conclusion: {analysis.conclusion}")

        return texts

    # =========================================================================
    # Step Notes Data
    # =========================================================================

    @staticmethod
    def get_step_notes(project) -> dict[int, str]:
        """
        Get notes from all steps as a dictionary.

        Args:
            project: ResearchProject instance

        Returns:
            Dict mapping step_index -> extracted text
        """
        notes = {}

        if project.step_notes:
            for step_idx, note_content in project.step_notes.items():
                text = ResearchDataService.extract_text_from_blocknote(note_content)
                if text:
                    notes[int(step_idx)] = text

        return notes

    @staticmethod
    def get_step_notes_text(project) -> list[str]:
        """
        Get step notes as a list of text strings.

        Args:
            project: ResearchProject instance

        Returns:
            List of text strings
        """
        notes = ResearchDataService.get_step_notes(project)
        return list(notes.values())

    # =========================================================================
    # Thesis Summary
    # =========================================================================

    @staticmethod
    def get_thesis_summary(project) -> ThesisSummary:
        """
        Get the investment thesis and decision summary.

        Args:
            project: ResearchProject instance

        Returns:
            ThesisSummary dataclass
        """
        return ThesisSummary(
            investment_thesis=project.investment_thesis,
            green_flags=project.green_flags or [],
            red_flags=project.red_flags or [],
            decision=project.decision,
            decision_confidence=project.decision_confidence,
            decision_notes=project.decision_notes
        )

    @staticmethod
    def get_thesis_text(project) -> list[str]:
        """
        Get thesis summary as text strings.

        Args:
            project: ResearchProject instance

        Returns:
            List of text strings
        """
        texts = []
        summary = ResearchDataService.get_thesis_summary(project)

        if summary.investment_thesis:
            texts.append(f"Investment Thesis: {blocknote_to_text(summary.investment_thesis)}")

        if summary.green_flags:
            texts.append("Key Positives: " + ", ".join(summary.green_flags))

        if summary.red_flags:
            texts.append("Key Risks: " + ", ".join(summary.red_flags))

        if summary.decision_notes:
            texts.append(f"Decision Notes: {summary.decision_notes}")

        return texts

    # =========================================================================
    # Combined Data
    # =========================================================================

    @staticmethod
    def get_all_text(project, include_metadata: bool = False) -> str:
        """
        Get ALL research text combined into a single string.

        Aggregates text from:
        - Free research questions and answers
        - Checklist questions and answers
        - Step notes
        - Investment thesis, green/red flags, decision notes

        Args:
            project: ResearchProject instance
            include_metadata: If True, include labels like "Question:", "Answer:"

        Returns:
            Combined text string
        """
        all_texts = []

        # 1. Free Research data
        free_research_texts = ResearchDataService.get_free_research_text(project)
        all_texts.extend(free_research_texts)

        # 2. Checklist data
        checklist_texts = ResearchDataService.get_checklist_text(project)
        all_texts.extend(checklist_texts)

        # 3. Step notes
        step_notes_texts = ResearchDataService.get_step_notes_text(project)
        all_texts.extend(step_notes_texts)

        # 4. Thesis summary
        thesis_texts = ResearchDataService.get_thesis_text(project)
        all_texts.extend(thesis_texts)

        combined = "\n\n".join(filter(None, all_texts))

        if not include_metadata:
            # Remove labels for cleaner text
            combined = combined.replace("Research Question: ", "")
            combined = combined.replace("Research Finding: ", "")
            combined = combined.replace("Checklist Question: ", "")
            combined = combined.replace("Answer: ", "")

        return combined

    @staticmethod
    def get_word_count(project) -> int:
        """
        Get the total word count of all research text.

        Args:
            project: ResearchProject instance

        Returns:
            Word count
        """
        text = ResearchDataService.get_all_text(project)
        return len(text.split())

    @staticmethod
    def get_research_stats(project) -> dict:
        """
        Get statistics about the research data.

        Args:
            project: ResearchProject instance

        Returns:
            Dict with counts and statistics
        """
        free_research = ResearchDataService.get_free_research_data(project)
        checklist = ResearchDataService.get_checklist_data(project)
        step_notes = ResearchDataService.get_step_notes(project)
        thesis = ResearchDataService.get_thesis_summary(project)

        return {
            'free_research_questions': len(free_research),
            'free_research_answered': len([q for q in free_research if q.status == 'answered']),
            'checklist_answers': len(checklist),
            'step_notes_count': len(step_notes),
            'has_thesis': bool(thesis.investment_thesis),
            'green_flags_count': len(thesis.green_flags),
            'red_flags_count': len(thesis.red_flags),
            'has_decision': bool(thesis.decision),
            'word_count': ResearchDataService.get_word_count(project),
        }
