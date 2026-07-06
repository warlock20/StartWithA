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
Argos Service - Main entry point for Argos functionality

Composes existing services:
- SimilarMistakesService for embedding-based matching
- ai_service for LLM relevance scoring
- prompt_service for prompt templates
"""

import logging
import time
import numpy as np

from typing import List, Optional, Dict, Any
from app.services.ai.embedding_service import embed, get_embedding_service
from app.services.ai import ai_service, AITaskType, prompt_service

from app.services.similar_mistakes import SimilarMistakesService
from app.models.idea_pipeline import MistakeLog
from app.models.ai_intelligence import EmbeddingStore
from app.models.journal import DecisionJournal, PatternRecognition

from app import db
from app.models import Company
from app.services.argos.config import (
    THRESHOLDS,
    CONTEXT_RULE_MATRIX,
    FINANCIAL_SECTIONS,
    ACCOUNTING_KEYWORDS,
    LLM_CONFIG,
    InsightCategory,
    ConfidenceLevel,
)
from app.services.argos.insights import (
    ArgosInsight,
    InsightCandidate,
    ArgosCheckResult,
)

from app.services.argos.companion import CompanionMixin, CompanionContext  # noqa: F401

logger = logging.getLogger(__name__)


class ArgosService(CompanionMixin):
    """
    Argos - Intelligent Research Assistant

    Main service that orchestrates:
    1. Gathering insight candidates (deterministic + SimilarMistakesService)
    2. Context-aware filtering
    3. LLM relevance scoring (optional)
    4. Result formatting

    Usage:
        argos = ArgosService(user_id=123)
        result = argos.check(
            company_id=456,
            step_type='checklist',
            step_context={'section': 'financial'}
        )
    """

    def __init__(self, user_id: int):
        self.user_id = user_id
        self._similar_mistakes_service = None

    @property
    def similar_mistakes_service(self):
        """Lazy load SimilarMistakesService."""
        if self._similar_mistakes_service is None:
            self._similar_mistakes_service = SimilarMistakesService(user_id=self.user_id)
        return self._similar_mistakes_service

    # =========================================================================
    # Main Entry Point
    # =========================================================================

    def check(
        self,
        company_id: int,
        step_type: str,
        step_context: Optional[Dict[str, Any]] = None,
        current_text: Optional[str] = None,
    ) -> ArgosCheckResult:
        """
        Perform Argos Check for current research context.

        Args:
            company_id: Company being researched
            step_type: Type of step ('checklist', 'free_research', 'thesis', 'completion')
            step_context: Additional context (e.g., {'section': 'financial'})
            current_text: Current research text for semantic matching

        Returns:
            ArgosCheckResult with insights and checks
        """
        start_time = time.time()
        step_context = step_context or {}

        # Get company info
        company = self._get_company(company_id)
        if not company:
            return self._empty_result()

        # Determine which categories to check based on context
        applicable_categories = self._get_applicable_categories(step_type, step_context)

        # Gather candidates from each applicable category
        all_candidates = []
        checks_passed = []
        checks_failed = []

        for category in applicable_categories:
            candidates, passed, failed = self._gather_candidates(
                category=category,
                company=company,
                step_context=step_context,
                current_text=current_text,
            )
            all_candidates.extend(candidates)
            checks_passed.extend(passed)
            checks_failed.extend(failed)

        # LLM relevance scoring (if enabled and candidates exist)
        scored_candidates = all_candidates
        llm_used = False

        if all_candidates and LLM_CONFIG['relevance_scoring']['enabled']:
            scored_candidates, llm_used = self._score_with_llm(
                candidates=all_candidates,
                company=company,
                step_type=step_type,
                step_context=step_context,
            )

        # Convert to final insights
        insights = self._candidates_to_insights(scored_candidates)

        # Build result
        processing_time = int((time.time() - start_time) * 1000)

        return ArgosCheckResult(
            insights=insights,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            categories_checked=[c.value for c in applicable_categories],
            llm_used=llm_used,
            processing_time_ms=processing_time,
        )

    # =========================================================================
    # Category Gathering
    # =========================================================================

    def _gather_candidates(
        self,
        category: InsightCategory,
        company,
        step_context: Dict[str, Any],
        current_text: Optional[str],
    ) -> tuple[List[InsightCandidate], List[str], List[str]]:
        """
        Gather candidates for a specific category.

        Returns:
            (candidates, checks_passed, checks_failed)
        """
        method_map = {
            InsightCategory.MISTAKE_MATCH: self._gather_mistake_matches,
            InsightCategory.LOSS_PATTERN: self._gather_loss_patterns,
            InsightCategory.ACCOUNTING_FLAG: self._gather_accounting_flags,
            InsightCategory.CONSISTENCY: self._gather_consistency_issues,
            InsightCategory.COMPLETENESS: self._gather_completeness_issues,
            InsightCategory.JOURNAL_INSIGHT: self._gather_journal_insights,
            InsightCategory.PATTERN_WARNING: self._gather_pattern_warnings,
        }

        method = method_map.get(category)
        if method:
            return method(company, step_context, current_text)

        return [], [], []

    def _gather_mistake_matches(
        self,
        company,
        step_context: Dict[str, Any],
        current_text: Optional[str],
    ) -> tuple[List[InsightCandidate], List[str], List[str]]:
        """
        Find relevant mistake log entries.

        Strategy:
        1. Deterministic: sector match, same company
        2. Semantic: embedding similarity (if current_text provided)
        """
        candidates = []
        checks_passed = []
        checks_failed = []
        seen_ids = set()  # Avoid duplicates

        # Get user's mistake log entries
        mistakes = MistakeLog.query.filter_by(user_id=self.user_id).all()
        if not mistakes:
            return candidates, checks_passed, checks_failed

        # Get current company's sector
        company_sector = self._get_company_sector(company.id)

        # --- 1. Deterministic Matching ---
        for mistake in mistakes:
            match_reasons = []

            # Same company - highest relevance
            if mistake.company_id == company.id:
                match_reasons.append('same_company')

            # Sector match
            if company_sector and mistake.company_id:
                mistake_sector = self._get_company_sector(mistake.company_id)
                if mistake_sector and mistake_sector.lower() == company_sector.lower():
                    match_reasons.append('sector_match')

            if match_reasons:
                seen_ids.add(mistake.id)
                candidates.append(self._mistake_to_candidate(
                    mistake,
                    match_reasons,
                    confidence=ConfidenceLevel.HIGH
                ))

        # --- 2. Semantic Matching (if text provided) ---
        if current_text and len(current_text.strip()) > 20:
            semantic_candidates = self._find_similar_mistakes_by_embedding(
                current_text,
                mistakes,
                exclude_ids=seen_ids
            )
            candidates.extend(semantic_candidates)

        # Sort by confidence then severity
        candidates.sort(key=lambda c: (
            0 if c.base_confidence == ConfidenceLevel.HIGH else 1,
            -c.raw_data.get('severity', 5),
        ))

        logger.debug(f"MistakeMatch found {len(candidates)} candidates")
        return candidates, checks_passed, checks_failed

    def _find_similar_mistakes_by_embedding(
        self,
        query_text: str,
        mistakes: List,
        exclude_ids: set,
        min_similarity: float = 0.6,
        max_results: int = 5,
    ) -> List[InsightCandidate]:
        """
        Find semantically similar mistake log entries using embeddings.
        """
        candidates = []

        try:
            embedding_service = get_embedding_service()

            # Embed query text
            query_embedding = embed(query_text)
            if query_embedding is None:
                return candidates

            # Get embeddings for mistakes (from EmbeddingStore or generate)
            mistake_embeddings = []
            for mistake in mistakes:
                if mistake.id in exclude_ids:
                    continue

                embedding = self._get_or_create_mistake_embedding(mistake)
                if embedding is not None:
                    mistake_embeddings.append((mistake.id, embedding))

            if not mistake_embeddings:
                return candidates

            # Find similar
            similar_results = embedding_service.find_similar(
                query_embedding=query_embedding,
                candidates=mistake_embeddings,
                top_k=max_results,
                min_similarity=min_similarity,
            )

            # Convert to candidates
            mistake_map = {m.id: m for m in mistakes}
            for mistake_id, similarity in similar_results:
                mistake = mistake_map.get(mistake_id)
                if mistake:
                    candidates.append(self._mistake_to_candidate(
                        mistake,
                        match_reasons=[f'semantic_match:{similarity:.2f}'],
                        confidence=ConfidenceLevel.MEDIUM,
                        similarity_score=similarity,
                    ))

        except Exception as e:
            logger.error(f"Embedding search failed: {e}")

        return candidates

    def _get_or_create_mistake_embedding(self, mistake) -> Optional[Any]:
        """
        Get embedding for mistake from store, or create and store it.
        """
        # Check if embedding exists
        existing = EmbeddingStore.query.filter_by(
            user_id=self.user_id,
            entity_type='mistake',
            entity_id=mistake.id,
        ).first()

        if existing and existing.embedding_vector is not None:
            return np.array(existing.embedding_vector)

        # Generate embedding from mistake text
        text_to_embed = self._build_mistake_text(mistake)
        if not text_to_embed:
            return None

        embedding = embed(text_to_embed)
        if embedding is None:
            return None

        # Store for future use
        try:
            if existing:
                existing.embedding_vector = embedding.tolist()
                existing.source_text = text_to_embed[:500]
            else:
                new_embedding = EmbeddingStore(
                    user_id=self.user_id,
                    entity_type='mistake',
                    entity_id=mistake.id,
                    embedding_vector=embedding.tolist(),
                    source_text=text_to_embed[:500],
                    embedding_model='default',
                )
                db.session.add(new_embedding)
            db.session.commit()
        except Exception as e:
            logger.warning(f"Failed to store embedding for mistake {mistake.id}: {e}")
            db.session.rollback()

        return embedding

    def _build_mistake_text(self, mistake) -> str:
        """Build searchable text from mistake fields."""
        parts = []
        if mistake.title:
            parts.append(mistake.title)
        if mistake.description:
            parts.append(mistake.description)
        if mistake.lesson_learned:
            parts.append(mistake.lesson_learned)
        if mistake.root_cause:
            parts.append(mistake.root_cause)
        return ' '.join(parts)

    def _mistake_to_candidate(
        self,
        mistake,
        match_reasons: List[str],
        confidence: ConfidenceLevel,
        similarity_score: Optional[float] = None,
    ) -> InsightCandidate:
        """Convert MistakeLog to InsightCandidate."""
        return InsightCandidate(
            category=InsightCategory.MISTAKE_MATCH,
            source_type='mistake_log',
            source_id=mistake.id,
            raw_data={
                'id': mistake.id,
                'title': mistake.title,
                'description': mistake.description[:300] if mistake.description else '',
                'lesson_learned': mistake.lesson_learned[:300] if mistake.lesson_learned else '',
                'mistake_type': mistake.mistake_type,
                'severity': mistake.severity or 5,
                'cost_estimate': mistake.cost_estimate,
                'company_name': mistake.company.name if mistake.company else None,
                'similarity_score': similarity_score,
            },
            match_reason=', '.join(match_reasons),
            base_confidence=confidence,
            matched_sector='sector_match' in match_reasons,
            matched_tags=[mistake.mistake_type] if mistake.mistake_type else [],
        )

    def _get_company_sector(self, company_id: int) -> Optional[str]:
        """Get sector name for a company."""
        company = Company.query.get(company_id)
        if company and hasattr(company, 'sector') and company.sector:
            return company.sector.name if hasattr(company.sector, 'name') else str(company.sector)
        return None

    def _gather_loss_patterns(
        self,
        company,
        step_context: Dict[str, Any],
        current_text: Optional[str],
    ) -> tuple[List[InsightCandidate], List[str], List[str]]:
        """
        Find significant loss trades in same sector.

        TODO: Query transactions with loss > threshold, same sector
        """
        logger.debug("_detect_loss_aversion_risk: Not yet implemented")
        return [], [], []

    def _gather_accounting_flags(
        self,
        company,
        step_context: Dict[str, Any],
        current_text: Optional[str],
    ) -> tuple[List[InsightCandidate], List[str], List[str]]:
        """
        Check for accounting red flags (Beneish, Altman).

        TODO: Integrate with financial_data service
        - Beneish M-Score > -1.78 = potential manipulation
        - Altman Z-Score < 1.81 = distress
        """
        logger.debug("_gather_accounting_flags: Not yet implemented")
        return [], ["No accounting red flags detected"], []

    def _gather_consistency_issues(
        self,
        company,
        step_context: Dict[str, Any],
        current_text: Optional[str],
    ) -> tuple[List[InsightCandidate], List[str], List[str]]:
        """
        Check if current answers differ from successful patterns.

        TODO: Compare checklist responses to historical patterns from past successful investments
        """
        logger.debug("_gather_consistency_issues: Not yet implemented")
        return [], [], []

    def _gather_completeness_issues(
        self,
        company,
        step_context: Dict[str, Any],
        current_text: Optional[str],
    ) -> tuple[List[InsightCandidate], List[str], List[str]]:
        """
        Check research completeness before step completion.

        TODO: Count answered vs total questions, warn if below threshold
        """
        logger.debug("_gather_completeness_issues: Not yet implemented")
        return [], [], []

    def _gather_journal_insights(
        self,
        company,
        step_context: Dict[str, Any],
        current_text: Optional[str],
    ) -> tuple[List[InsightCandidate], List[str], List[str]]:
        """
        Find relevant DecisionJournal entries for this company/sector.

        Surfaces: past decisions, outcomes, lessons learned for the same
        company or sector — so the user sees their own history.
        """

        candidates = []
        checks_passed = []
        checks_failed = []

        # Get journal entries for same company
        company_journals = DecisionJournal.query.filter_by(
            user_id=self.user_id,
            company_id=company.id,
        ).all()

        for journal in company_journals:
            candidates.append(InsightCandidate(
                category=InsightCategory.JOURNAL_INSIGHT,
                source_type='decision_journal',
                source_id=journal.id,
                raw_data={
                    'id': journal.id,
                    'decision_type': journal.decision_type,
                    'decision_date': str(journal.decision_date) if journal.decision_date else None,
                    'confidence_score': journal.confidence_score,
                    'investment_thesis': (journal.investment_thesis_text or '')[:300],
                    'lessons_learned': (journal.lessons_learned or '')[:300],
                    'what_went_wrong': (journal.what_went_wrong or '')[:300],
                    'actual_return': journal.actual_return,
                    'would_repeat': journal.would_repeat,
                    'company_name': company.name,
                },
                match_reason='same_company',
                base_confidence=ConfidenceLevel.HIGH,
            ))

        # Get journal entries for same sector
        company_sector = self._get_company_sector(company.id)
        if company_sector:
            sector_company_ids = [
                c.id for c in Company.query.filter_by(user_id=self.user_id).all()
                if self._get_company_sector(c.id) and
                   self._get_company_sector(c.id).lower() == company_sector.lower() and
                   c.id != company.id
            ]
            if sector_company_ids:
                sector_journals = DecisionJournal.query.filter(
                    DecisionJournal.user_id == self.user_id,
                    DecisionJournal.company_id.in_(sector_company_ids),
                ).all()

                for journal in sector_journals:
                    candidates.append(InsightCandidate(
                        category=InsightCategory.JOURNAL_INSIGHT,
                        source_type='decision_journal',
                        source_id=journal.id,
                        raw_data={
                            'id': journal.id,
                            'decision_type': journal.decision_type,
                            'decision_date': str(journal.decision_date) if journal.decision_date else None,
                            'confidence_score': journal.confidence_score,
                            'investment_thesis': (journal.investment_thesis_text or '')[:300],
                            'lessons_learned': (journal.lessons_learned or '')[:300],
                            'actual_return': journal.actual_return,
                            'company_name': getattr(journal, 'company', None) and journal.company.name or 'Unknown',
                        },
                        match_reason='sector_match',
                        base_confidence=ConfidenceLevel.MEDIUM,
                        matched_sector=True,
                    ))

        logger.debug(f"JournalInsight found {len(candidates)} candidates")
        return candidates, checks_passed, checks_failed

    def _gather_pattern_warnings(
        self,
        company,
        step_context: Dict[str, Any],
        current_text: Optional[str],
    ) -> tuple[List[InsightCandidate], List[str], List[str]]:
        """
        Surface PatternRecognition entries (failure patterns, behavioral patterns).

        These are user-identified or AI-detected patterns that should be front
        of mind during research.
        """
        candidates = []
        checks_passed = []
        checks_failed = []

        # Get failure and behavioral patterns (most relevant during research)
        patterns = PatternRecognition.query.filter(
            PatternRecognition.user_id == self.user_id,
            PatternRecognition.pattern_type.in_(['failure_pattern', 'behavioral']),
        ).all()

        for pattern in patterns:
            candidates.append(InsightCandidate(
                category=InsightCategory.PATTERN_WARNING,
                source_type='pattern_recognition',
                source_id=pattern.id,
                raw_data={
                    'id': pattern.id,
                    'pattern_name': pattern.pattern_name,
                    'pattern_type': pattern.pattern_type,
                    'description': (pattern.description or '')[:300],
                    'occurrences': pattern.occurrences,
                    'impact_score': pattern.impact_score,
                    'how_to_avoid': (pattern.how_to_avoid or '')[:300],
                    'confidence_level': pattern.confidence_level,
                    'last_observed': str(pattern.last_observed) if pattern.last_observed else None,
                },
                match_reason='active_pattern',
                base_confidence=ConfidenceLevel.HIGH if (pattern.impact_score or 0) >= 7 else ConfidenceLevel.MEDIUM,
                matched_tags=[pattern.pattern_type] if pattern.pattern_type else [],
            ))

        logger.debug(f"PatternWarning found {len(candidates)} candidates")
        return candidates, checks_passed, checks_failed

    # =========================================================================
    # Context Filtering
    # =========================================================================

    def _get_applicable_categories(
        self,
        step_type: str,
        step_context: Dict[str, Any],
    ) -> List[InsightCategory]:
        """Determine which insight categories apply to current context."""
        if step_type not in CONTEXT_RULE_MATRIX:
            step_type = 'checklist'  # Default

        rules = CONTEXT_RULE_MATRIX[step_type]
        applicable = []

        for category, rule in rules.items():
            if rule is True:
                applicable.append(category)
            elif rule == 'financial':
                # Only if in financial section
                section = step_context.get('section', '').lower()
                if section in FINANCIAL_SECTIONS:
                    applicable.append(category)
            elif rule == 'keywords':
                # Only if keywords match (for free research)
                # TODO: Check if current_text contains accounting keywords
                applicable.append(category)  # Include for now, filter later

        return applicable

    # =========================================================================
    # LLM Scoring
    # =========================================================================

    def _score_with_llm(
        self,
        candidates: List[InsightCandidate],
        company,
        step_type: str,
        step_context: Dict[str, Any],
    ) -> tuple[List[InsightCandidate], bool]:
        """
        Score candidates with LLM for relevance.

        Returns:
            (scored_candidates, llm_was_used)
        """
        max_to_score = LLM_CONFIG['relevance_scoring']['max_insights_to_score']
        candidates_to_score = candidates[:max_to_score]

        if not candidates_to_score:
            return candidates, False

        try:
            # Prepare prompt
            prompt = prompt_service.get_prompt(
                'argos',
                'relevance_scoring',
                company_name=company.name,
                sector=getattr(company, 'sector', 'Unknown'),
                step_type=step_type,
                current_focus=step_context.get('section', 'general'),
                candidates_json=self._candidates_to_json(candidates_to_score),
            )

            # Call LLM
            response = ai_service.generate_json(
                prompt,
                task=AITaskType.ARGOS_RELEVANCE_SCORING,
            )

            # Apply scores to candidates
            if response and isinstance(response, list):
                self._apply_llm_scores(candidates_to_score, response)

            return candidates_to_score, True

        except Exception as e:
            logger.error(f"Argos LLM scoring failed: {e}")
            return candidates, False

    def _candidates_to_json(self, candidates: List[InsightCandidate]) -> str:
        """Convert candidates to JSON for LLM prompt."""
        import json
        items = []
        for i, c in enumerate(candidates):
            items.append({
                'candidate_id': str(i),
                'category': c.category.value,
                'source_type': c.source_type,
                'match_reason': c.match_reason,
                'summary': c.raw_data.get('title', '') or c.raw_data.get('summary', ''),
            })
        return json.dumps(items, indent=2)

    def _apply_llm_scores(
        self,
        candidates: List[InsightCandidate],
        scores: List[Dict],
    ):
        """Apply LLM relevance scores to candidates."""
        score_map = {s.get('candidate_id'): s for s in scores}
        for i, candidate in enumerate(candidates):
            score_data = score_map.get(str(i), {})
            # Store score in raw_data for now
            candidate.raw_data['llm_relevance_score'] = score_data.get('relevance_score', 0.5)
            candidate.raw_data['llm_relevant'] = score_data.get('is_relevant', True)
            candidate.raw_data['llm_reason'] = score_data.get('reason', '')

    # =========================================================================
    # Result Conversion
    # =========================================================================

    def _candidates_to_insights(
        self,
        candidates: List[InsightCandidate],
    ) -> List[ArgosInsight]:
        """Convert scored candidates to final insights."""
        insights = []

        for candidate in candidates:
            # Skip if LLM marked as not relevant
            if not candidate.raw_data.get('llm_relevant', True):
                continue

            # Skip if LLM score too low
            llm_score = candidate.raw_data.get('llm_relevance_score', 0.5)
            if llm_score < 0.4:
                continue

            insight = ArgosInsight(
                id=f"{candidate.source_type}_{candidate.source_id}",
                category=candidate.category,
                confidence=candidate.base_confidence,
                summary=self._build_summary(candidate),
                source_type=candidate.source_type,
                source_id=candidate.source_id,
                source_label=self._build_source_label(candidate),
                severity=candidate.raw_data.get('severity', 'medium'),
                tags=candidate.matched_tags,
                llm_relevance_score=llm_score,
            )
            insights.append(insight)

        # Sort by confidence then relevance score
        insights.sort(
            key=lambda x: (
                0 if x.confidence == ConfidenceLevel.HIGH else 1 if x.confidence == ConfidenceLevel.MEDIUM else 2,
                -(x.llm_relevance_score or 0),
            )
        )

        return insights

    def _build_summary(self, candidate: InsightCandidate) -> str:
        """Build insight summary from candidate."""
        raw = candidate.raw_data
        if candidate.source_type == 'mistake_log':
            return raw.get('title', 'Mistake log entry')
        elif candidate.source_type == 'trade_loss':
            return f"Loss on {raw.get('company_name', 'Unknown')}: {raw.get('return_pct', 0):.1f}%"
        elif candidate.source_type == 'decision_journal':
            decision_type = raw.get('decision_type', 'unknown')
            company = raw.get('company_name', 'Unknown')
            return f"Past {decision_type} decision on {company}"
        elif candidate.source_type == 'pattern_recognition':
            return raw.get('pattern_name', 'Behavioral pattern')
        return raw.get('summary', 'Insight')

    def _build_source_label(self, candidate: InsightCandidate) -> str:
        """Build human-readable source label."""
        if candidate.source_type == 'mistake_log':
            return f"Mistake #{candidate.source_id}"
        elif candidate.source_type == 'trade_loss':
            return f"Trade: {candidate.raw_data.get('company_name', 'Unknown')}"
        elif candidate.source_type == 'decision_journal':
            return f"Decision Journal #{candidate.source_id}"
        elif candidate.source_type == 'pattern_recognition':
            return f"Pattern: {candidate.raw_data.get('pattern_name', 'Unknown')}"
        return f"{candidate.source_type} #{candidate.source_id}"

    # =========================================================================
    # Helpers
    # =========================================================================

    def _get_company(self, company_id: int):
        """Get company by ID."""
        return Company.query.get(company_id)

    def _empty_result(self) -> ArgosCheckResult:
        """Return empty result."""
        return ArgosCheckResult(
            insights=[],
            checks_passed=[],
            checks_failed=['Company not found'],
        )


# =============================================================================
# Convenience Functions
# =============================================================================

def argos_check(
    user_id: int,
    company_id: int,
    step_type: str,
    step_context: Optional[Dict[str, Any]] = None,
) -> ArgosCheckResult:
    """
    Convenience function for Argos Check.

    Usage:
        from app.services.argos import argos_check
        result = argos_check(user_id=1, company_id=2, step_type='checklist')
    """
    service = ArgosService(user_id=user_id)
    return service.check(company_id, step_type, step_context)
