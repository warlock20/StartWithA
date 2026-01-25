"""
Argos Matchers - Deterministic filters for insight candidates

Each matcher handles one InsightCategory.
Returns InsightCandidate objects for LLM scoring.
"""

from .mistake_matcher import MistakeMatcher
from .loss_pattern import LossPatternMatcher
from .accounting_flags import AccountingFlagChecker
from .consistency import ConsistencyChecker
from .completeness import CompletenessChecker

__all__ = [
    'MistakeMatcher',
    'LossPatternMatcher',
    'AccountingFlagChecker',
    'ConsistencyChecker',
    'CompletenessChecker',
]
