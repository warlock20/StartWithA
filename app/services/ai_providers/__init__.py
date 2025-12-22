"""
AI Provider Factory - Unified interface for Claude, Gemini, and ML models

This module defines the routing logic for AI tasks:
- Claude: Quality-critical reasoning (thesis analysis, insights, warnings)
- Gemini: Cost-effective high-volume tasks (document Q&A, extraction)
- Local ML: Pattern detection and scoring
"""

from enum import Enum
from typing import Optional


class AIProvider(Enum):
    """Available AI providers"""
    CLAUDE = "claude"
    GEMINI = "gemini"
    LOCAL_ML = "local_ml"


class AITaskType(Enum):
    """Map tasks to optimal providers"""

    # Claude-optimal tasks (quality-critical, reasoning-heavy)
    THESIS_ANALYSIS = "thesis_analysis"
    PATTERN_EXPLANATION = "pattern_explanation"
    DECISION_REVIEW = "decision_review"
    INSIGHT_GENERATION = "insight_generation"
    WARNING_GENERATION = "warning_generation"

    # Gemini-optimal tasks (cost-effective, high-volume)
    DOCUMENT_QA = "document_qa"
    TEXT_EXTRACTION = "text_extraction"
    SIMPLE_ANALYSIS = "simple_analysis"
    EMBEDDING_GENERATION = "embedding_generation"

    # ML-optimal tasks (pattern detection, scoring)
    QUALITY_SCORING = "quality_scoring"
    PATTERN_DETECTION = "pattern_detection"
    SIMILARITY_MATCHING = "similarity_matching"
    OUTCOME_PREDICTION = "outcome_prediction"


# Task to provider mapping
TASK_PROVIDER_MAP = {
    # Claude for quality-critical
    AITaskType.THESIS_ANALYSIS: AIProvider.CLAUDE,
    AITaskType.PATTERN_EXPLANATION: AIProvider.CLAUDE,
    AITaskType.DECISION_REVIEW: AIProvider.CLAUDE,
    AITaskType.INSIGHT_GENERATION: AIProvider.CLAUDE,
    AITaskType.WARNING_GENERATION: AIProvider.CLAUDE,

    # Gemini for cost-effective
    AITaskType.DOCUMENT_QA: AIProvider.GEMINI,
    AITaskType.TEXT_EXTRACTION: AIProvider.GEMINI,
    AITaskType.SIMPLE_ANALYSIS: AIProvider.GEMINI,
    AITaskType.EMBEDDING_GENERATION: AIProvider.GEMINI,

    # ML for detection/scoring
    AITaskType.QUALITY_SCORING: AIProvider.LOCAL_ML,
    AITaskType.PATTERN_DETECTION: AIProvider.LOCAL_ML,
    AITaskType.SIMILARITY_MATCHING: AIProvider.LOCAL_ML,
    AITaskType.OUTCOME_PREDICTION: AIProvider.LOCAL_ML,
}


def get_provider_for_task(task: AITaskType, force_provider: Optional[AIProvider] = None) -> AIProvider:
    """
    Get the optimal provider for a task, with optional override

    Args:
        task: The AI task type
        force_provider: Optional provider to force use of (overrides default mapping)

    Returns:
        The provider to use for this task
    """
    if force_provider:
        return force_provider
    return TASK_PROVIDER_MAP.get(task, AIProvider.GEMINI)


__all__ = [
    'AIProvider',
    'AITaskType',
    'TASK_PROVIDER_MAP',
    'get_provider_for_task',
]
