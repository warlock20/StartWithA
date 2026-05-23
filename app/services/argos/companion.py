"""
Argos Companion Features

Mixin class that adds Research Companion capabilities to ArgosService:
- build_research_context: Assemble enriched context from project + history
- generate_brief: Pre-session research brief
- ask_companion: Facts-only live chat during research
- generate_counter_evidence: Devil's advocate for findings
- wrap_up_session: Session summary with gaps and next steps
"""

import logging
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any

from app.models.idea_pipeline import MistakeLog
from app.models.journal import DecisionJournal, PatternRecognition
from app.models.research import ResearchProject, FreeResearchQuestion
from app.models import Company
from app.services.ai import ai_service, prompt_service

logger = logging.getLogger(__name__)


@dataclass
class CompanionContext:
    """Assembled context for companion features. Used by all companion methods."""
    company_name: str
    company_id: int
    sector_name: str
    step_name: str
    step_description: str
    step_index: int
    research_questions: str
    prior_findings: str
    red_flags: str
    green_flags: str
    investment_thesis: str
    journal_summary: str
    mistake_summary: str
    pattern_summary: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CompanionMixin:
    """
    Companion features mixed into ArgosService.

    Expects self.user_id to be set by the host class.
    """

    # =========================================================================
    # Companion Features
    # =========================================================================

    def build_research_context(self, project_id: int, step_index: Optional[int] = None) -> CompanionContext:
        """
        Build enriched context from ResearchProject + history data.

        Assembles: company, step, questions, findings, flags, thesis,
        plus mistake log, journal entries, and patterns.
        """
        project = ResearchProject.query.get(project_id)
        if not project or project.user_id != self.user_id:
            raise ValueError(f"Project {project_id} not found or access denied")

        company = project.company
        if step_index is None:
            step_index = project.current_step_index or 0

        # Get step info from project workflow
        step = project.get_step(step_index)
        step_name = step.get('name', f'Step {step_index + 1}') if step else f'Step {step_index + 1}'
        step_description = step.get('description', '') if step else ''

        # Get research questions for this step
        research_questions = self._extract_research_questions(project, step, step_index)

        # Get prior findings
        prior_findings = self._format_prior_findings(project, step_index)

        # Get flags
        red_flags = ', '.join(project.red_flags or []) or 'None identified yet'
        green_flags = ', '.join(project.green_flags or []) or 'None identified yet'

        # Thesis
        investment_thesis = project.investment_thesis_text or 'Not yet formed'

        # Sector
        sector_name = 'Unknown'
        if company and hasattr(company, 'sector') and company.sector:
            sector_name = company.sector.name if hasattr(company.sector, 'name') else str(company.sector)

        # --- Enrichment: mistakes, journals, patterns ---
        journal_summary = self._build_journal_summary(company.id, sector_name)
        mistake_summary = self._build_mistake_summary(company.id, sector_name)
        pattern_summary = self._build_pattern_summary()

        return CompanionContext(
            company_name=company.name if company else 'Unknown',
            company_id=company.id if company else 0,
            sector_name=sector_name,
            step_name=step_name,
            step_description=step_description,
            step_index=step_index,
            research_questions=research_questions,
            prior_findings=prior_findings,
            red_flags=red_flags,
            green_flags=green_flags,
            investment_thesis=investment_thesis,
            journal_summary=journal_summary,
            mistake_summary=mistake_summary,
            pattern_summary=pattern_summary,
        )

    def generate_brief(self, context: CompanionContext) -> str:
        """Generate a pre-session research brief."""
        try:
            prompt = prompt_service.get_prompt(
                'companion', 'research_brief', **context.to_dict()
            )
            return ai_service.generate_text(prompt)
        except Exception as e:
            logger.error(f"Failed to generate research brief: {e}")
            return f"Could not generate brief: {e}"

    def ask_companion(
        self,
        context: CompanionContext,
        user_question: str,
        conversation_history: List[Dict[str, str]],
    ) -> str:
        """Answer a user question during research. Facts only, no opinions."""
        try:
            history_text = '\n'.join(
                f"{msg['role'].upper()}: {msg['content']}"
                for msg in conversation_history[-10:]
            ) or 'No prior conversation'

            prompt = prompt_service.get_prompt(
                'companion', 'live_companion',
                company_name=context.company_name,
                sector_name=context.sector_name,
                step_name=context.step_name,
                research_questions=context.research_questions,
                current_findings=context.prior_findings,
                investment_thesis=context.investment_thesis,
                history_context=f"Mistakes: {context.mistake_summary}\nPatterns: {context.pattern_summary}\nPast decisions: {context.journal_summary}",
                conversation_history=history_text,
                user_question=user_question,
            )
            return ai_service.generate_text(prompt)
        except Exception as e:
            logger.error(f"Companion chat failed: {e}")
            return f"Could not process question: {e}"

    def wrap_up_session(
        self,
        context: CompanionContext,
        session_findings: List[str],
        duration_minutes: int,
        counter_evidence: List[str] = None,
    ) -> str:
        """Generate a session wrap-up summary."""
        try:
            prompt = prompt_service.get_prompt(
                'companion', 'session_wrapup',
                company_name=context.company_name,
                step_name=context.step_name,
                duration_minutes=str(duration_minutes),
                research_questions=context.research_questions,
                session_findings='\n'.join(session_findings) or 'No findings added this session',
                all_findings=context.prior_findings,
                counter_evidence='\n'.join(counter_evidence or []) or 'None generated',
            )
            return ai_service.generate_text(prompt)
        except Exception as e:
            logger.error(f"Session wrap-up failed: {e}")
            return f"Could not generate wrap-up: {e}"

    def get_warnings_by_company(self, company_id: int) -> List[Dict[str, Any]]:
        """
        Get proactive warnings for a company — pattern warnings + journal insights + mistake history.
        Pure DB queries, zero token cost. Works with company_id directly (no project required).
        """
        company = Company.query.get(company_id)
        if not company or company.user_id != self.user_id:
            return []

        warnings = []

        # Sector
        sector_name = 'Unknown'
        if hasattr(company, 'sector') and company.sector:
            sector_name = company.sector.name if hasattr(company.sector, 'name') else str(company.sector)

        # Pattern warnings (behavioral + failure patterns)
        patterns = PatternRecognition.query.filter(
            PatternRecognition.user_id == self.user_id,
            PatternRecognition.pattern_type.in_(['failure_pattern', 'behavioral']),
        ).order_by(PatternRecognition.impact_score.desc()).limit(5).all()

        for p in patterns:
            severity = 'high' if (p.impact_score or 0) >= 7 else 'medium' if (p.impact_score or 0) >= 4 else 'low'
            warnings.append({
                'type': 'pattern_warning',
                'severity': severity,
                'title': p.pattern_name,
                'message': (p.description or '')[:200],
                'detail': (p.how_to_avoid or '')[:200],
                'icon': 'bi-exclamation-triangle-fill',
                'source_id': p.id,
                'occurrences': p.occurrences,
                'impact_score': p.impact_score,
            })

        # Journal insights (past decisions for this company)
        journal_entries = DecisionJournal.query.filter_by(
            user_id=self.user_id, company_id=company.id,
        ).order_by(DecisionJournal.decision_date.desc()).limit(3).all()

        for j in journal_entries:
            severity = 'info'
            if j.actual_return is not None and j.actual_return < -10:
                severity = 'high'
            elif j.actual_return is not None and j.actual_return < 0:
                severity = 'medium'

            lesson = (j.lessons_learned or j.what_went_wrong or '')[:200]
            if lesson:
                warnings.append({
                    'type': 'journal_insight',
                    'severity': severity,
                    'title': f'Past {j.decision_type} decision on {company.name}',
                    'message': lesson,
                    'detail': f'Confidence: {j.confidence_score}/10' + (f', Return: {j.actual_return:.1f}%' if j.actual_return is not None else ''),
                    'icon': 'bi-journal-text',
                    'source_id': j.id,
                })

        # Mistake history for this company/sector
        mistakes = list(MistakeLog.query.filter_by(
            user_id=self.user_id, company_id=company.id,
        ).limit(3).all())

        if sector_name and sector_name != 'Unknown':
            sector_companies = Company.query.filter_by(user_id=self.user_id).all()
            sector_company_ids = [
                c.id for c in sector_companies
                if hasattr(c, 'sector') and c.sector
                and (c.sector.name if hasattr(c.sector, 'name') else str(c.sector)).lower() == sector_name.lower()
                and c.id != company.id
            ]
            if sector_company_ids:
                sector_mistakes = MistakeLog.query.filter(
                    MistakeLog.user_id == self.user_id,
                    MistakeLog.company_id.in_(sector_company_ids),
                ).limit(3).all()
                mistakes.extend(sector_mistakes)

        for m in mistakes[:5]:
            warnings.append({
                'type': 'mistake_history',
                'severity': 'high',
                'title': m.title,
                'message': (m.lesson_learned or 'No lesson recorded')[:200],
                'detail': f'Company: {m.company.name if m.company else "Unknown"}',
                'icon': 'bi-lightning-fill',
                'source_id': m.id,
            })

        return warnings

    def get_warnings(self, project_id: int) -> List[Dict[str, Any]]:
        """
        Get proactive warnings for a project — pattern warnings + journal insights + mistake history.
        Pure DB queries, zero token cost. Designed for auto-loading on page load.
        Delegates to get_warnings_by_company() for the actual queries.
        """
        project = ResearchProject.query.get(project_id)
        if not project or project.user_id != self.user_id:
            return []

        company = project.company
        if not company:
            return []

        return self.get_warnings_by_company(company.id)

    # =========================================================================
    # Companion Context Helpers
    # =========================================================================

    def _extract_research_questions(self, project, step, step_index: int) -> str:
        """Extract research questions for the current step."""
        questions = []
        if step and step.get('config', {}).get('questions'):
            questions.extend(step['config']['questions'])
        if step and step.get('type') == 'free_research':
            free_questions = FreeResearchQuestion.query.filter_by(
                project_id=project.id, step_index=step_index,
            ).all()
            questions.extend([q.question_text for q in free_questions])
        return '\n'.join(f"- {q}" for q in questions) if questions else 'No specific questions defined for this step'

    def _format_prior_findings(self, project, current_step_index: int) -> str:
        """Format findings from prior steps."""
        findings = []
        if project.key_findings:
            findings.extend(project.key_findings)
        if project.step_results:
            for idx_str, result in project.step_results.items():
                if int(idx_str) < current_step_index:
                    if isinstance(result, str):
                        findings.append(result[:200])
                    elif isinstance(result, dict):
                        findings.append(str(result.get('summary', ''))[:200])
        if project.step_notes:
            for idx_str, notes in project.step_notes.items():
                if int(idx_str) < current_step_index and notes and notes != '[SKIPPED]':
                    if isinstance(notes, str):
                        findings.append(notes[:200])
        return '\n'.join(f"- {f}" for f in findings[:20]) if findings else 'No findings yet'

    def _build_journal_summary(self, company_id: int, sector_name: str) -> str:
        """Summarize relevant journal entries."""
        entries = DecisionJournal.query.filter_by(
            user_id=self.user_id, company_id=company_id,
        ).all()
        if not entries:
            return 'No prior decisions for this company'
        parts = []
        for e in entries[:5]:
            outcome = f', outcome: {e.actual_return:.1f}%' if e.actual_return is not None else ''
            parts.append(f"- {e.decision_type} (confidence: {e.confidence_score}/10{outcome})")
        return '\n'.join(parts)

    def _build_mistake_summary(self, company_id: int, sector_name: str) -> str:
        """Summarize relevant mistakes."""
        mistakes = list(MistakeLog.query.filter_by(
            user_id=self.user_id, company_id=company_id,
        ).all())
        if sector_name and sector_name != 'Unknown':
            sector_companies = Company.query.filter_by(user_id=self.user_id).all()
            sector_company_ids = [
                c.id for c in sector_companies
                if hasattr(c, 'sector') and c.sector
                and (c.sector.name if hasattr(c.sector, 'name') else str(c.sector)).lower() == sector_name.lower()
                and c.id != company_id
            ]
            if sector_company_ids:
                sector_mistakes = MistakeLog.query.filter(
                    MistakeLog.user_id == self.user_id,
                    MistakeLog.company_id.in_(sector_company_ids),
                ).all()
                mistakes.extend(sector_mistakes)
        if not mistakes:
            return 'No past mistakes for this company/sector'
        parts = []
        for m in mistakes[:5]:
            parts.append(f"- {m.title}: {(m.lesson_learned or 'No lesson recorded')[:100]}")
        return '\n'.join(parts)

    def _build_pattern_summary(self) -> str:
        """Summarize active behavioral and failure patterns."""
        patterns = PatternRecognition.query.filter(
            PatternRecognition.user_id == self.user_id,
            PatternRecognition.pattern_type.in_(['failure_pattern', 'behavioral']),
        ).order_by(PatternRecognition.impact_score.desc()).limit(5).all()
        if not patterns:
            return 'No patterns identified yet'
        parts = []
        for p in patterns:
            avoid = f' — {p.how_to_avoid[:100]}' if p.how_to_avoid else ''
            parts.append(f"- {p.pattern_name} (impact: {p.impact_score}/10, seen {p.occurrences}x){avoid}")
        return '\n'.join(parts)
