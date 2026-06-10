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
