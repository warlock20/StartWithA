"""
Argos - Intelligent Research Assistant

Blind spot detector that predicts & suggests based on user's own data.
Personal data only. Reactive first. Context-aware rules.

Composes:
- SimilarMistakesService for embedding-based matching
- ai_service for LLM relevance scoring
- prompt_service for prompt templates

Usage:
    from app.services.argos import ArgosService, argos_check

    # Quick check
    result = argos_check(
        user_id=1,
        company_id=2,
        step_type='checklist',
        step_context={'section': 'financial'}
    )

    # Or use service directly
    argos = ArgosService(user_id=1)
    result = argos.check(company_id=2, step_type='checklist')

    # Access results
    for insight in result.insights:
        print(f"{insight.confidence.value}: {insight.summary}")
"""

from .core import ArgosService, argos_check
from .companion import CompanionContext
from .config import InsightCategory, ConfidenceLevel
from .insights import ArgosInsight, ArgosCheckResult, InsightCandidate
from .triggers import PreComputeTrigger

__all__ = [
    # Main service
    'ArgosService',
    'argos_check',

    # Companion
    'CompanionContext',

    # Data classes
    'ArgosInsight',
    'ArgosCheckResult',
    'InsightCandidate',

    # Enums
    'InsightCategory',
    'ConfidenceLevel',

    # Triggers
    'PreComputeTrigger',
]
