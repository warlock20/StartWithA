"""
Argos Insight Data Classes

Data flow:
    DB Query → InsightCandidate → (LLM scores) → ArgosInsight → ArgosCheckResult → UI
    PreComputedInsight ← stored on data events
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any

from .config import InsightCategory, ConfidenceLevel


@dataclass
class ArgosInsight:
    """Final output to UI. What user sees in the modal."""

    id: str
    category: InsightCategory
    confidence: ConfidenceLevel
    summary: str
    source_type: str                     # 'mistake_log', 'trade_loss', etc.
    source_id: int
    source_label: str                    # "Mistake #12", "Trade: ABC Corp"

    explanation: Optional[str] = None    # LLM-generated detail
    related_company: Optional[str] = None
    severity: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    llm_relevance_score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'category': self.category.value,
            'confidence': self.confidence.value,
            'summary': self.summary,
            'source_type': self.source_type,
            'source_id': self.source_id,
            'source_label': self.source_label,
            'explanation': self.explanation,
            'related_company': self.related_company,
            'severity': self.severity,
            'tags': self.tags,
        }


@dataclass
class InsightCandidate:
    """Intermediate stage. Output from deterministic filters, input to LLM."""

    category: InsightCategory
    source_type: str
    source_id: int
    raw_data: Dict[str, Any]
    match_reason: str                    # Why filter matched
    base_confidence: ConfidenceLevel

    matched_sector: bool = False
    matched_tags: List[str] = field(default_factory=list)
    matched_keywords: List[str] = field(default_factory=list)


@dataclass
class ArgosCheckResult:
    """Container for entire Argos Check response."""

    insights: List[ArgosInsight]
    checks_passed: List[str]             # ["No accounting flags"]
    checks_failed: List[str]

    total_insights: int = 0
    high_confidence_count: int = 0
    medium_confidence_count: int = 0
    low_confidence_count: int = 0

    categories_checked: List[str] = field(default_factory=list)
    llm_used: bool = False
    processing_time_ms: int = 0

    def __post_init__(self):
        self.total_insights = len(self.insights)
        self.high_confidence_count = sum(
            1 for i in self.insights if i.confidence == ConfidenceLevel.HIGH
        )
        self.medium_confidence_count = sum(
            1 for i in self.insights if i.confidence == ConfidenceLevel.MEDIUM
        )
        self.low_confidence_count = sum(
            1 for i in self.insights if i.confidence == ConfidenceLevel.LOW
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'insights': [i.to_dict() for i in self.insights],
            'checks_passed': self.checks_passed,
            'checks_failed': self.checks_failed,
            'summary': {
                'total': self.total_insights,
                'high': self.high_confidence_count,
                'medium': self.medium_confidence_count,
                'low': self.low_confidence_count,
            },
            'meta': {
                'categories_checked': self.categories_checked,
                'llm_used': self.llm_used,
                'processing_time_ms': self.processing_time_ms,
            },
        }


@dataclass
class PreComputedInsight:
    """What gets stored in DB for fast retrieval."""

    user_id: int
    source_type: str
    source_id: int

    # Matching criteria
    sector: Optional[str]
    tags: List[str]
    company_ids: List[int]
    relevance_keywords: List[str]

    # Content
    summary: str
    confidence: ConfidenceLevel
    severity: str

    # Feedback
    times_surfaced: int = 0
    times_helpful: int = 0
    times_not_helpful: int = 0

    def to_model_dict(self) -> Dict[str, Any]:
        """For DB model creation"""
        return {
            'user_id': self.user_id,
            'source_type': self.source_type,
            'source_id': self.source_id,
            'sector': self.sector,
            'tags': self.tags,
            'company_ids': self.company_ids,
            'relevance_keywords': self.relevance_keywords,
            'summary': self.summary,
            'confidence': self.confidence.value,
            'severity': self.severity,
        }
