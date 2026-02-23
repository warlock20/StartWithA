"""
Argos Configuration

Thresholds, weights, and rule mappings.
All values are configurable per user in the future.
"""

from enum import Enum
from typing import Dict, List, Set


class ConfidenceLevel(Enum):
    """Confidence levels for insights"""
    HIGH = 'high'
    MEDIUM = 'medium'
    LOW = 'low'


class InsightCategory(Enum):
    """Categories of Argos insights"""
    MISTAKE_MATCH = 'mistake_match'
    LOSS_PATTERN = 'loss_pattern'
    ACCOUNTING_FLAG = 'accounting_flag'
    CONSISTENCY = 'consistency'
    COMPLETENESS = 'completeness'
    JOURNAL_INSIGHT = 'journal_insight'
    PATTERN_WARNING = 'pattern_warning'


# =============================================================================
# Thresholds (configurable per user in future)
# =============================================================================

THRESHOLDS = {
    # Minimum data before Argos activates
    'min_investments_for_patterns': 5,
    'min_mistakes_for_matching': 1,

    # Loss pattern detection
    'significant_loss_percent': -30,  # Losses worse than this trigger insights
    'severe_loss_percent': -50,       # Losses worse than this = HIGH confidence

    # Accounting red flags
    'beneish_m_score_threshold': -1.78,  # Above this = potential manipulation
    'altman_z_score_danger': 1.81,       # Below this = distress zone
    'altman_z_score_grey': 2.99,         # Below this = grey zone

    # Completeness
    'min_completion_percent': 80,  # Warn if below this before step complete
}


# =============================================================================
# Context-Rule Matrix
# =============================================================================

# Which insight categories apply to which step types
CONTEXT_RULE_MATRIX: Dict[str, Dict[str, bool | str]] = {
    'checklist': {
        InsightCategory.MISTAKE_MATCH: True,
        InsightCategory.LOSS_PATTERN: True,
        InsightCategory.ACCOUNTING_FLAG: 'financial',  # Only for financial sections
        InsightCategory.CONSISTENCY: True,
        InsightCategory.COMPLETENESS: False,  # Only at completion
        InsightCategory.JOURNAL_INSIGHT: True,
        InsightCategory.PATTERN_WARNING: True,
    },
    'free_research': {
        InsightCategory.MISTAKE_MATCH: True,
        InsightCategory.LOSS_PATTERN: True,
        InsightCategory.ACCOUNTING_FLAG: 'keywords',  # Only if keywords match
        InsightCategory.CONSISTENCY: False,
        InsightCategory.COMPLETENESS: False,
        InsightCategory.JOURNAL_INSIGHT: True,
        InsightCategory.PATTERN_WARNING: True,
    },
    'thesis': {
        InsightCategory.MISTAKE_MATCH: True,
        InsightCategory.LOSS_PATTERN: True,
        InsightCategory.ACCOUNTING_FLAG: True,
        InsightCategory.CONSISTENCY: False,
        InsightCategory.COMPLETENESS: False,
        InsightCategory.JOURNAL_INSIGHT: True,
        InsightCategory.PATTERN_WARNING: True,
    },
    'completion': {
        InsightCategory.MISTAKE_MATCH: True,
        InsightCategory.LOSS_PATTERN: True,
        InsightCategory.ACCOUNTING_FLAG: True,
        InsightCategory.CONSISTENCY: False,
        InsightCategory.COMPLETENESS: True,
        InsightCategory.JOURNAL_INSIGHT: True,
        InsightCategory.PATTERN_WARNING: True,
    },
}


# Sections within checklist that trigger accounting flags
FINANCIAL_SECTIONS = {
    'financial_analysis',
    'financial',
    'valuation',
    'accounting',
    'balance_sheet',
    'income_statement',
    'cash_flow',
}

# Keywords that trigger accounting flag check in free research
ACCOUNTING_KEYWORDS = {
    'revenue', 'earnings', 'profit', 'margin', 'debt', 'cash',
    'accrual', 'receivable', 'inventory', 'goodwill', 'impairment',
    'audit', 'restatement', 'fraud', 'manipulation', 'aggressive',
}


# =============================================================================
# Pre-compute Relevance Weights
# =============================================================================

# Events and their relevance for pre-computing
EVENT_RELEVANCE = {
    'mistake_logged': {
        'always_compute': True,
        'weight': 10,
    },
    'trade_closed_loss': {
        'always_compute': False,  # Only if loss > threshold
        'weight': 8,
    },
    'trade_closed_profit': {
        'always_compute': False,  # Usually not insight-worthy
        'weight': 2,
    },
    'research_completed': {
        'always_compute': False,  # Only if has outcome data
        'weight': 5,
    },
    'thesis_updated': {
        'always_compute': False,
        'weight': 3,
    },
}


# =============================================================================
# Confidence Calculation Rules
# =============================================================================

CONFIDENCE_RULES = {
    InsightCategory.MISTAKE_MATCH: {
        'base': ConfidenceLevel.HIGH,  # User explicitly logged this
    },
    InsightCategory.LOSS_PATTERN: {
        'base': ConfidenceLevel.MEDIUM,
        'boost_if': {
            'loss_percent_below': -50,  # Boost to HIGH if severe loss
        },
    },
    InsightCategory.ACCOUNTING_FLAG: {
        'base': ConfidenceLevel.MEDIUM,
    },
    InsightCategory.CONSISTENCY: {
        'base': ConfidenceLevel.LOW,
    },
    InsightCategory.COMPLETENESS: {
        'base': ConfidenceLevel.LOW,
    },
    InsightCategory.JOURNAL_INSIGHT: {
        'base': ConfidenceLevel.MEDIUM,
    },
    InsightCategory.PATTERN_WARNING: {
        'base': ConfidenceLevel.HIGH,  # User-identified patterns are high value
    },
}


# =============================================================================
# LLM Configuration
# =============================================================================

LLM_CONFIG = {
    'relevance_scoring': {
        'enabled': True,
        'max_insights_to_score': 10,  # Don't send more than this to LLM
    },
    'explanation_generation': {
        'enabled': True,
        'on_demand_only': True,  # Only when user clicks "Details"
    },
}
