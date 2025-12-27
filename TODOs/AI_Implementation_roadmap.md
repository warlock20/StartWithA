# AI Implementation Roadmap
## Investment Checklist Platform - From Data to Intelligence

---

## Master Plan Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        IMPLEMENTATION TIMELINE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  WEEK 1-2          WEEK 3-4          WEEK 5-6          WEEK 7-8            │
│  ─────────         ─────────         ─────────         ─────────           │
│  Foundation        Data Pipeline     Intelligence      Portfolio            │
│                                                                             │
│  ┌─────────┐      ┌─────────┐       ┌─────────┐       ┌─────────┐          │
│  │ Tables  │ ───▶ │ Scoring │ ───▶  │ Warnings│ ───▶  │ Insights│          │
│  │ + APIs  │      │ + Track │       │ + Match │       │ + Learn │          │
│  └─────────┘      └─────────┘       └─────────┘       └─────────┘          │
│                                                                             │
│  PHASE 1 FOUNDATION    PHASE 1 COMPLETE    PHASE 2 COMPLETE   PHASE 3     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## How Technical Work Maps to Features

```
┌────────────────────────────────────────────────────────────────────────────┐
│                    TECHNICAL → FEATURE MAPPING                              │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  TECHNICAL WORK                          ENABLES FEATURE                   │
│  ══════════════                          ═══════════════                   │
│                                                                            │
│  research_outcome table        ───▶      "Your researched investments      │
│                                           return 15% more than impulse"    │
│                                                                            │
│  ai_insight table              ───▶      Persistent warnings that learn    │
│                                           from user feedback               │
│                                                                            │
│  embedding_store + pgvector    ───▶      "This company is similar to X     │
│                                           which you lost money on"         │
│                                                                            │
│  Claude API integration        ───▶      High-quality thesis analysis      │
│                                           and natural explanations         │
│                                                                            │
│  ML pattern detection          ───▶      "You hold losers 2x longer        │
│                                           than winners (disposition bias)" │
│                                                                            │
│  research_quality_score        ───▶      "Research depth score: 73/100"    │
│                                           with specific improvement tips   │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

# WEEK 1-2: Foundation Layer : THIS IS COMPLETE 

## Goals
- [ ] New database tables for AI features
- [ ] Claude API integration alongside Gemini
- [ ] Basic data collection pipeline

## Day 1-2: Database Migration

### New Tables to Create

```sql
-- ============================================
-- TABLE 1: research_outcome
-- Purpose: Link research quality to investment results
-- This is the CORE table for Phase 1
-- ============================================

CREATE TABLE research_outcome (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    
    -- Link to research (one of these will be set)
    research_session_id INTEGER REFERENCES research_session(id) ON DELETE SET NULL,
    research_project_id INTEGER REFERENCES research_project(id) ON DELETE SET NULL,
    
    -- Link to decision and portfolio
    decision_journal_id INTEGER REFERENCES decision_journal(id) ON DELETE SET NULL,
    company_id INTEGER NOT NULL REFERENCES company(id) ON DELETE CASCADE,
    
    -- ===== RESEARCH METRICS (captured at decision time) =====
    research_quality_score FLOAT,           -- 0-100 composite score
    questions_answered INTEGER DEFAULT 0,
    questions_total INTEGER DEFAULT 0,
    documents_analyzed INTEGER DEFAULT 0,
    ai_assists_used INTEGER DEFAULT 0,
    research_duration_minutes INTEGER DEFAULT 0,
    checklist_completion_pct FLOAT DEFAULT 0,
    
    -- Research depth indicators
    had_financial_analysis BOOLEAN DEFAULT FALSE,
    had_competitive_analysis BOOLEAN DEFAULT FALSE,
    had_management_review BOOLEAN DEFAULT FALSE,
    had_valuation_model BOOLEAN DEFAULT FALSE,
    
    -- ===== DECISION METRICS (captured at buy) =====
    decision_date DATE,
    entry_price DECIMAL(15, 4),
    position_size DECIMAL(15, 2),
    initial_thesis TEXT,
    confidence_at_entry INTEGER,            -- 1-10 scale
    expected_return_pct FLOAT,
    expected_hold_months INTEGER,
    
    -- ===== OUTCOME METRICS (updated over time) =====
    current_return_pct FLOAT,
    exit_date DATE,
    exit_price DECIMAL(15, 4),
    realized_return_pct FLOAT,
    actual_hold_days INTEGER,
    
    -- Thesis accuracy (how well predictions matched reality)
    thesis_accuracy_score FLOAT,            -- 0-100
    checkpoints_met INTEGER DEFAULT 0,
    checkpoints_total INTEGER DEFAULT 0,
    thesis_still_valid BOOLEAN DEFAULT TRUE,
    
    -- ===== LEARNING METRICS (computed by ML) =====
    outcome_category VARCHAR(20),           -- 'big_win', 'small_win', 'small_loss', 'big_loss'
    predictive_factors JSONB,               -- Which research factors predicted this outcome
    correlation_confidence FLOAT,
    lessons_extracted JSONB,                -- AI-generated lessons
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    outcome_recorded_at TIMESTAMP,
    last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT valid_research CHECK (
        research_session_id IS NOT NULL OR research_project_id IS NOT NULL OR
        (research_session_id IS NULL AND research_project_id IS NULL)  -- Allow no-research purchases
    )
);

-- Indexes for common queries
CREATE INDEX idx_research_outcome_user ON research_outcome(user_id);
CREATE INDEX idx_research_outcome_company ON research_outcome(company_id);
CREATE INDEX idx_research_outcome_date ON research_outcome(decision_date);
CREATE INDEX idx_research_outcome_category ON research_outcome(outcome_category);


-- ============================================
-- TABLE 2: ai_insight
-- Purpose: Store AI-generated warnings and suggestions
-- Enables learning from user feedback
-- ============================================

CREATE TABLE ai_insight (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    
    -- What triggered this insight
    insight_type VARCHAR(50) NOT NULL,      -- 'warning', 'suggestion', 'pattern', 'reminder'
    trigger_type VARCHAR(50) NOT NULL,      -- 'research_start', 'buy_transaction', 'thesis_review', 'periodic'
    
    -- Context: where does this insight apply?
    context_type VARCHAR(50),               -- 'company', 'research', 'portfolio', 'journal'
    context_id INTEGER,                     -- ID of the related entity
    company_id INTEGER REFERENCES company(id) ON DELETE SET NULL,
    
    -- The insight content
    title VARCHAR(200) NOT NULL,
    insight_text TEXT NOT NULL,
    supporting_data JSONB,                  -- Evidence/data that supports this insight
    
    -- AI metadata
    ai_provider VARCHAR(50),                -- 'claude', 'gemini', 'ml_model'
    model_version VARCHAR(50),
    confidence FLOAT,                       -- 0-1 confidence score
    generation_prompt TEXT,                 -- For debugging/improvement
    
    -- Related patterns/history
    related_mistake_ids INTEGER[],          -- Links to mistake_log entries
    related_outcome_ids INTEGER[],          -- Links to research_outcome entries
    similar_past_insights INTEGER[],        -- Links to previous similar insights
    
    -- User interaction tracking
    was_shown BOOLEAN DEFAULT FALSE,
    shown_at TIMESTAMP,
    user_action VARCHAR(50),                -- 'dismissed', 'acknowledged', 'applied', 'helpful', 'not_helpful'
    user_feedback TEXT,
    action_taken_at TIMESTAMP,
    
    -- Outcome validation (did the warning prove correct?)
    was_validated BOOLEAN,
    validation_outcome VARCHAR(50),         -- 'correct', 'incorrect', 'partially_correct', 'unknown'
    validated_at TIMESTAMP,
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    expires_at TIMESTAMP,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_ai_insight_user ON ai_insight(user_id);
CREATE INDEX idx_ai_insight_type ON ai_insight(insight_type);
CREATE INDEX idx_ai_insight_context ON ai_insight(context_type, context_id);
CREATE INDEX idx_ai_insight_active ON ai_insight(user_id, is_active, created_at);
CREATE INDEX idx_ai_insight_validation ON ai_insight(was_validated, validation_outcome);


-- ============================================
-- TABLE 3: embedding_store
-- Purpose: Store vector embeddings for similarity matching
-- Requires pgvector extension
-- ============================================

-- First, enable pgvector extension (run once)
-- CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE embedding_store (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    
    -- What entity does this embedding represent?
    entity_type VARCHAR(50) NOT NULL,       -- 'thesis', 'mistake', 'research_note', 'company_summary'
    entity_id INTEGER NOT NULL,
    
    -- The embedding vector (384 dimensions for MiniLM, 1536 for OpenAI)
    embedding_vector vector(384),           -- Using sentence-transformers default
    
    -- Source text that was embedded
    source_text TEXT,
    text_hash VARCHAR(64),                  -- For deduplication
    
    -- Metadata
    embedding_model VARCHAR(100) NOT NULL,  -- 'all-MiniLM-L6-v2', 'text-embedding-ada-002'
    embedding_version INTEGER DEFAULT 1,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    UNIQUE(user_id, entity_type, entity_id, embedding_model)
);

-- Index for similarity search (using IVFFlat for speed)
CREATE INDEX idx_embedding_vector ON embedding_store 
    USING ivfflat (embedding_vector vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_embedding_entity ON embedding_store(entity_type, entity_id);
CREATE INDEX idx_embedding_user ON embedding_store(user_id);


-- ============================================
-- TABLE 4: ml_prediction_log
-- Purpose: Track ML model predictions for validation
-- Enables model improvement over time
-- ============================================

CREATE TABLE ml_prediction_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    
    -- Model info
    model_name VARCHAR(100) NOT NULL,       -- 'research_quality', 'bias_detector', 'outcome_predictor'
    model_version VARCHAR(50) NOT NULL,
    
    -- Prediction details
    prediction_type VARCHAR(50) NOT NULL,   -- 'score', 'classification', 'probability'
    input_features JSONB NOT NULL,          -- Features used for prediction
    
    -- Prediction output
    predicted_value FLOAT,
    predicted_label VARCHAR(100),
    prediction_probabilities JSONB,         -- For multi-class predictions
    confidence FLOAT,
    
    -- Context
    context_type VARCHAR(50),               -- 'research', 'transaction', 'portfolio'
    context_id INTEGER,
    
    -- Validation (filled in later when outcome is known)
    actual_value FLOAT,
    actual_label VARCHAR(100),
    prediction_error FLOAT,                 -- For regression: actual - predicted
    was_correct BOOLEAN,                    -- For classification
    validated_at TIMESTAMP,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_ml_prediction_user ON ml_prediction_log(user_id);
CREATE INDEX idx_ml_prediction_model ON ml_prediction_log(model_name, model_version);
CREATE INDEX idx_ml_prediction_validation ON ml_prediction_log(model_name, was_correct);
```

## Day 3-4: Claude API Integration

### Updated LLM Service Architecture

```python
# app/services/ai_providers/__init__.py
"""
AI Provider Factory - Unified interface for Claude, Gemini, and ML models
"""

from enum import Enum
from typing import Dict, Any, Optional
import os


class AIProvider(Enum):
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
    """Get the optimal provider for a task, with optional override"""
    if force_provider:
        return force_provider
    return TASK_PROVIDER_MAP.get(task, AIProvider.GEMINI)
```

```python
# app/services/ai_providers/claude_provider.py
"""
Claude (Anthropic) API Provider
Used for quality-critical tasks: thesis analysis, insights, warnings
"""

import os
import logging
from typing import Dict, Any, Optional, List
import anthropic

logger = logging.getLogger(__name__)


class ClaudeProvider:
    """Claude API wrapper for investment analysis tasks"""
    
    def __init__(self):
        self.api_key = os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            logger.warning("ANTHROPIC_API_KEY not set - Claude provider unavailable")
            self.client = None
        else:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        
        # Model selection
        self.default_model = "claude-sonnet-4-20250514"  # Good balance of quality/cost
        self.premium_model = "claude-sonnet-4-20250514"    # For critical analysis
    
    def is_available(self) -> bool:
        """Check if Claude API is configured"""
        return self.client is not None
    
    def generate_thesis_analysis(
        self,
        company_name: str,
        thesis_text: str,
        research_data: Dict[str, Any],
        historical_context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Analyze investment thesis quality and identify potential issues
        
        Returns:
            {
                'quality_assessment': str,
                'strengths': List[str],
                'weaknesses': List[str],
                'blind_spots': List[str],
                'suggested_questions': List[str],
                'confidence_adjustment': int,  # -2 to +2
                'risk_flags': List[str]
            }
        """
        if not self.is_available():
            raise RuntimeError("Claude API not available")
        
        # Build context from historical patterns
        history_context = ""
        if historical_context:
            history_context = f"""
            
HISTORICAL CONTEXT FROM USER'S PAST INVESTMENTS:
- Similar companies researched: {historical_context.get('similar_companies', 'None')}
- Past mistakes in this sector: {historical_context.get('sector_mistakes', 'None')}
- User's typical blind spots: {historical_context.get('blind_spots', 'None')}
"""
        
        prompt = f"""You are an expert investment analyst reviewing a thesis for {company_name}.

INVESTMENT THESIS:
{thesis_text}

RESEARCH DATA SUMMARY:
- Questions answered: {research_data.get('questions_answered', 0)}/{research_data.get('questions_total', 0)}
- Documents analyzed: {research_data.get('documents_analyzed', 0)}
- Key findings: {research_data.get('key_findings', 'Not provided')}
- Identified risks: {research_data.get('identified_risks', 'Not provided')}
{history_context}

Analyze this thesis and provide:

1. QUALITY ASSESSMENT: Brief overall assessment (2-3 sentences)

2. STRENGTHS: What aspects of this thesis are well-reasoned? (list 2-4)

3. WEAKNESSES: What logical gaps or unsupported assumptions exist? (list 2-4)

4. BLIND SPOTS: What important factors might the investor be missing? (list 2-3)

5. SUGGESTED QUESTIONS: What additional research questions should be answered? (list 3-5)

6. CONFIDENCE ADJUSTMENT: Should the investor's confidence be adjusted?
   - Return a number from -2 (significantly reduce) to +2 (can increase)
   - 0 = confidence level seems appropriate

7. RISK FLAGS: Any red flags that warrant serious attention? (list if any)

Respond in JSON format."""

        try:
            message = self.client.messages.create(
                model=self.default_model,
                max_tokens=2000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            # Parse response
            response_text = message.content[0].text
            
            # Try to parse as JSON, fall back to structured extraction
            import json
            try:
                return json.loads(response_text)
            except json.JSONDecodeError:
                # Extract structured data from text response
                return self._parse_thesis_response(response_text)
                
        except Exception as e:
            logger.error(f"Claude thesis analysis error: {e}")
            raise
    
    def generate_warning(
        self,
        warning_context: Dict[str, Any],
        user_patterns: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate a contextual warning based on detected patterns
        
        Args:
            warning_context: Current situation details
            user_patterns: Historical patterns from user's data
            
        Returns:
            {
                'title': str,
                'warning_text': str,
                'severity': str,  # 'low', 'medium', 'high'
                'evidence': List[str],
                'suggested_action': str,
                'related_past_mistakes': List[str]
            }
        """
        if not self.is_available():
            raise RuntimeError("Claude API not available")
        
        prompt = f"""You are a thoughtful investment advisor helping an investor avoid past mistakes.

CURRENT SITUATION:
{warning_context.get('situation_description', '')}
Company: {warning_context.get('company_name', 'Unknown')}
Action being considered: {warning_context.get('action', 'Unknown')}

DETECTED PATTERN:
{warning_context.get('pattern_description', '')}

USER'S HISTORICAL PATTERNS:
- Past similar situations: {user_patterns.get('similar_situations', 'None recorded')}
- Outcomes in similar cases: {user_patterns.get('outcomes', 'Unknown')}
- Common mistakes: {user_patterns.get('common_mistakes', 'None recorded')}

Generate a helpful, non-judgmental warning that:
1. Clearly explains the concern
2. References specific past experience if relevant
3. Suggests a concrete action
4. Is encouraging, not discouraging

Respond in JSON format with: title, warning_text, severity (low/medium/high), evidence (list), suggested_action, related_past_mistakes (list)"""

        try:
            message = self.client.messages.create(
                model=self.default_model,
                max_tokens=1000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            import json
            response_text = message.content[0].text
            return json.loads(response_text)
            
        except Exception as e:
            logger.error(f"Claude warning generation error: {e}")
            raise
    
    def explain_pattern(
        self,
        pattern_type: str,
        pattern_data: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> str:
        """
        Generate a human-friendly explanation of a detected behavioral pattern
        
        Used when ML detects a pattern and we need Claude to explain it
        """
        if not self.is_available():
            raise RuntimeError("Claude API not available")
        
        prompt = f"""You are a behavioral finance expert helping an investor understand their patterns.

DETECTED PATTERN: {pattern_type}

PATTERN DATA:
{pattern_data}

USER CONTEXT:
- Investment experience: {user_context.get('experience_level', 'Unknown')}
- Portfolio size: {user_context.get('portfolio_size', 'Unknown')}
- Investment style: {user_context.get('investment_style', 'Unknown')}

Write a brief (2-3 paragraph), friendly explanation that:
1. Explains what this pattern means in plain English
2. Why it matters for investment performance
3. One specific thing they could try differently

Be supportive, not critical. Use "we" language to feel collaborative."""

        try:
            message = self.client.messages.create(
                model=self.default_model,
                max_tokens=500,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            return message.content[0].text
            
        except Exception as e:
            logger.error(f"Claude pattern explanation error: {e}")
            raise
    
    def _parse_thesis_response(self, text: str) -> Dict[str, Any]:
        """Fallback parser for non-JSON responses"""
        # Basic extraction logic
        return {
            'quality_assessment': text[:500],
            'strengths': [],
            'weaknesses': [],
            'blind_spots': [],
            'suggested_questions': [],
            'confidence_adjustment': 0,
            'risk_flags': []
        }
```

```python
# app/services/ai_providers/unified_ai_service.py
"""
Unified AI Service - Routes requests to optimal provider
"""

from typing import Dict, Any, Optional, List
from .claude_provider import ClaudeProvider
from ..llm_service import UnifiedLLMService, LLMProvider
from . import AIProvider, AITaskType, get_provider_for_task
import logging

logger = logging.getLogger(__name__)


class UnifiedAIService:
    """
    Main AI service that routes to optimal provider based on task
    """
    
    def __init__(self):
        self.claude = ClaudeProvider()
        self.gemini = UnifiedLLMService(LLMProvider.GEMINI)
        self._ml_models = {}  # Lazy-loaded ML models
    
    def analyze_thesis(
        self,
        company_name: str,
        thesis_text: str,
        research_data: Dict[str, Any],
        historical_context: Optional[Dict] = None,
        force_provider: Optional[AIProvider] = None
    ) -> Dict[str, Any]:
        """
        Analyze investment thesis - routes to Claude by default
        """
        provider = get_provider_for_task(AITaskType.THESIS_ANALYSIS, force_provider)
        
        if provider == AIProvider.CLAUDE and self.claude.is_available():
            return self.claude.generate_thesis_analysis(
                company_name, thesis_text, research_data, historical_context
            )
        else:
            # Fallback to Gemini
            logger.info("Falling back to Gemini for thesis analysis")
            return self._gemini_thesis_analysis(
                company_name, thesis_text, research_data
            )
    
    def generate_insight(
        self,
        insight_type: str,
        context: Dict[str, Any],
        user_history: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate AI insight/warning - routes to Claude by default
        """
        if self.claude.is_available():
            return self.claude.generate_warning(context, user_history)
        else:
            return self._gemini_insight(insight_type, context)
    
    def answer_research_question(
        self,
        question: str,
        documents: List[str],
        company_context: Dict[str, Any]
    ) -> str:
        """
        Answer research question - routes to Gemini by default (cost-effective)
        """
        prompt = self._build_research_prompt(question, documents, company_context)
        return self.gemini.generate_content(prompt)
    
    def calculate_research_quality(
        self,
        research_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate research quality score - uses ML model
        """
        return self._get_ml_model('research_quality').predict(research_metrics)
    
    def detect_behavioral_patterns(
        self,
        user_id: int,
        transaction_history: List[Dict],
        research_history: List[Dict]
    ) -> List[Dict[str, Any]]:
        """
        Detect behavioral biases - ML detection + Claude explanation
        """
        # Step 1: ML detects patterns
        patterns = self._get_ml_model('bias_detector').detect(
            transaction_history, research_history
        )
        
        # Step 2: Claude explains each pattern (if significant)
        explained_patterns = []
        for pattern in patterns:
            if pattern['confidence'] > 0.7:  # Only explain high-confidence patterns
                if self.claude.is_available():
                    explanation = self.claude.explain_pattern(
                        pattern['type'],
                        pattern['data'],
                        {'user_id': user_id}
                    )
                    pattern['explanation'] = explanation
            explained_patterns.append(pattern)
        
        return explained_patterns
    
    def find_similar_situations(
        self,
        current_situation: str,
        user_id: int,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find similar past situations using embeddings
        """
        # Generate embedding for current situation
        embedding = self._generate_embedding(current_situation)
        
        # Search similar embeddings
        return self._search_similar_embeddings(user_id, embedding, top_k)
    
    def _get_ml_model(self, model_name: str):
        """Lazy-load ML models"""
        if model_name not in self._ml_models:
            from .ml_models import load_model
            self._ml_models[model_name] = load_model(model_name)
        return self._ml_models[model_name]
    
    def _generate_embedding(self, text: str) -> List[float]:
        """Generate text embedding using sentence-transformers"""
        from sentence_transformers import SentenceTransformer
        
        if not hasattr(self, '_embedding_model'):
            self._embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        return self._embedding_model.encode(text).tolist()
    
    def _search_similar_embeddings(
        self,
        user_id: int,
        embedding: List[float],
        top_k: int
    ) -> List[Dict]:
        """Search for similar embeddings in database"""
        from app import db
        
        # Using pgvector similarity search
        query = """
            SELECT entity_type, entity_id, source_text,
                   1 - (embedding_vector <=> %s::vector) as similarity
            FROM embedding_store
            WHERE user_id = %s
            ORDER BY embedding_vector <=> %s::vector
            LIMIT %s
        """
        
        results = db.session.execute(
            query, [embedding, user_id, embedding, top_k]
        ).fetchall()
        
        return [
            {
                'entity_type': r[0],
                'entity_id': r[1],
                'text': r[2],
                'similarity': r[3]
            }
            for r in results
        ]
    
    def _build_research_prompt(
        self,
        question: str,
        documents: List[str],
        context: Dict
    ) -> str:
        """Build prompt for research Q&A"""
        doc_text = "\n\n---\n\n".join(documents[:3])  # Limit to 3 docs
        
        return f"""You are a financial analyst assistant. Answer the question based on the provided documents.

COMPANY: {context.get('company_name', 'Unknown')}
SECTOR: {context.get('sector', 'Unknown')}

DOCUMENTS:
{doc_text}

QUESTION:
{question}

Provide a clear, factual answer based only on the documents. If the information is not in the documents, say so."""
    
    def _gemini_thesis_analysis(
        self,
        company_name: str,
        thesis_text: str,
        research_data: Dict
    ) -> Dict[str, Any]:
        """Fallback thesis analysis using Gemini"""
        prompt = f"""Analyze this investment thesis for {company_name}:

THESIS: {thesis_text}

RESEARCH DATA: {research_data}

Provide JSON with: quality_assessment, strengths (list), weaknesses (list), suggested_questions (list)"""
        
        return self.gemini.generate_json(prompt)
    
    def _gemini_insight(
        self,
        insight_type: str,
        context: Dict
    ) -> Dict[str, Any]:
        """Fallback insight generation using Gemini"""
        prompt = f"""Generate an investment insight of type '{insight_type}':

CONTEXT: {context}

Provide JSON with: title, insight_text, severity, suggested_action"""
        
        return self.gemini.generate_json(prompt)


# Singleton instance
_ai_service = None

def get_ai_service() -> UnifiedAIService:
    """Get singleton AI service instance"""
    global _ai_service
    if _ai_service is None:
        _ai_service = UnifiedAIService()
    return _ai_service
```

## Day 5-7: Research Quality Scoring System

```python
# app/services/research_quality.py
"""
Research Quality Scoring System
Phase 1 Core: Measure and track research quality
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class ResearchQualityScore:
    """Research quality assessment result"""
    overall_score: float          # 0-100
    completeness_score: float     # How much of checklist completed
    depth_score: float            # Quality of answers
    breadth_score: float          # Variety of analysis types
    time_score: float             # Appropriate time invested
    document_score: float         # Document analysis depth
    
    grade: str                    # A, B, C, D, F
    improvement_tips: List[str]
    comparison_to_average: float  # % vs user's average


class ResearchQualityCalculator:
    """
    Calculate research quality scores
    
    This is the foundation for Phase 1 - measuring research quality
    so we can later correlate it with outcomes
    """
    
    # Scoring weights
    WEIGHTS = {
        'completeness': 0.25,
        'depth': 0.25,
        'breadth': 0.20,
        'time': 0.15,
        'documents': 0.15
    }
    
    # Minimum thresholds for "good" research
    THRESHOLDS = {
        'min_questions_pct': 0.7,      # Answer at least 70% of questions
        'min_time_minutes': 30,         # Spend at least 30 minutes
        'max_time_minutes': 480,        # More than 8 hours shows diminishing returns
        'min_documents': 1,             # Analyze at least 1 document
        'ideal_documents': 5,           # 5+ documents is thorough
    }
    
    def calculate_score(
        self,
        research_session_id: Optional[int] = None,
        research_project_id: Optional[int] = None,
        metrics: Optional[Dict[str, Any]] = None
    ) -> ResearchQualityScore:
        """
        Calculate comprehensive research quality score
        
        Can be called with either:
        - research_session_id (for checklist-based research)
        - research_project_id (for template-based research)
        - metrics dict (for manual calculation)
        """
        
        if metrics is None:
            metrics = self._gather_metrics(research_session_id, research_project_id)
        
        # Calculate component scores
        completeness = self._score_completeness(metrics)
        depth = self._score_depth(metrics)
        breadth = self._score_breadth(metrics)
        time = self._score_time(metrics)
        documents = self._score_documents(metrics)
        
        # Weighted overall score
        overall = (
            completeness * self.WEIGHTS['completeness'] +
            depth * self.WEIGHTS['depth'] +
            breadth * self.WEIGHTS['breadth'] +
            time * self.WEIGHTS['time'] +
            documents * self.WEIGHTS['documents']
        )
        
        # Get improvement tips
        tips = self._generate_tips(completeness, depth, breadth, time, documents, metrics)
        
        # Get user's average for comparison
        user_avg = self._get_user_average(metrics.get('user_id'))
        comparison = ((overall - user_avg) / user_avg * 100) if user_avg > 0 else 0
        
        return ResearchQualityScore(
            overall_score=round(overall, 1),
            completeness_score=round(completeness, 1),
            depth_score=round(depth, 1),
            breadth_score=round(breadth, 1),
            time_score=round(time, 1),
            document_score=round(documents, 1),
            grade=self._score_to_grade(overall),
            improvement_tips=tips,
            comparison_to_average=round(comparison, 1)
        )
    
    def _gather_metrics(
        self,
        session_id: Optional[int],
        project_id: Optional[int]
    ) -> Dict[str, Any]:
        """Gather metrics from database"""
        from app.models import (
            ChecklistAnalysis, ChecklistAnswer,
            ResearchProject, WorkSession
        )
        
        metrics = {
            'questions_answered': 0,
            'questions_total': 0,
            'answer_lengths': [],
            'satisfaction_ratings': [],
            'time_spent_minutes': 0,
            'documents_analyzed': 0,
            'ai_assists_used': 0,
            'had_financial_analysis': False,
            'had_competitive_analysis': False,
            'had_management_review': False,
            'had_valuation': False,
            'user_id': None
        }
        
        if session_id:
            session = ChecklistAnalysis.query.get(session_id)
            if session:
                metrics['user_id'] = session.user_id
                answers = ChecklistAnswer.query.filter_by(
                    checklist_analysis_id=session_id
                ).all()
                
                metrics['questions_total'] = session.checklist.items.count()
                metrics['questions_answered'] = len([a for a in answers if a.response_text])
                metrics['answer_lengths'] = [len(a.response_text or '') for a in answers]
                metrics['satisfaction_ratings'] = [
                    a.satisfaction_status for a in answers 
                    if a.satisfaction_status
                ]
        
        if project_id:
            project = ResearchProject.query.get(project_id)
            if project:
                metrics['user_id'] = project.user_id
                
                # Get work session data
                work_sessions = WorkSession.query.filter_by(
                    research_project_id=project_id
                ).all()
                
                metrics['time_spent_minutes'] = sum(
                    ws.duration_minutes or 0 for ws in work_sessions
                )
                
                # Analyze step types
                if project.step_notes:
                    notes = project.step_notes
                    metrics['had_financial_analysis'] = any(
                        'financial' in str(n).lower() for n in notes.values()
                    )
                    metrics['had_competitive_analysis'] = any(
                        'compet' in str(n).lower() for n in notes.values()
                    )
                    metrics['had_management_review'] = any(
                        'management' in str(n).lower() for n in notes.values()
                    )
        
        return metrics
    
    def _score_completeness(self, metrics: Dict) -> float:
        """Score based on % of questions answered"""
        if metrics['questions_total'] == 0:
            return 50.0  # Neutral if no questions
        
        pct = metrics['questions_answered'] / metrics['questions_total']
        
        if pct >= 0.9:
            return 100.0
        elif pct >= 0.7:
            return 70.0 + (pct - 0.7) * 150  # 70-100 range
        elif pct >= 0.5:
            return 50.0 + (pct - 0.5) * 100  # 50-70 range
        else:
            return pct * 100  # 0-50 range
    
    def _score_depth(self, metrics: Dict) -> float:
        """Score based on answer quality"""
        scores = []
        
        # Average answer length (longer often means more thorough)
        if metrics['answer_lengths']:
            avg_length = sum(metrics['answer_lengths']) / len(metrics['answer_lengths'])
            # 200+ chars is good, 500+ is excellent
            length_score = min(100, avg_length / 5)
            scores.append(length_score)
        
        # Satisfaction ratings (if using satisfaction tracking)
        if metrics['satisfaction_ratings']:
            # Convert satisfaction to score
            sat_map = {'satisfied': 100, 'neutral': 60, 'unsatisfied': 30}
            sat_scores = [sat_map.get(s, 50) for s in metrics['satisfaction_ratings']]
            scores.append(sum(sat_scores) / len(sat_scores))
        
        return sum(scores) / len(scores) if scores else 50.0
    
    def _score_breadth(self, metrics: Dict) -> float:
        """Score based on variety of analysis types"""
        analysis_types = [
            metrics.get('had_financial_analysis', False),
            metrics.get('had_competitive_analysis', False),
            metrics.get('had_management_review', False),
            metrics.get('had_valuation', False),
        ]
        
        completed = sum(analysis_types)
        return (completed / len(analysis_types)) * 100
    
    def _score_time(self, metrics: Dict) -> float:
        """Score based on time invested (with diminishing returns)"""
        minutes = metrics.get('time_spent_minutes', 0)
        
        if minutes < self.THRESHOLDS['min_time_minutes']:
            # Too little time
            return (minutes / self.THRESHOLDS['min_time_minutes']) * 60
        elif minutes <= 120:
            # Good range (30-120 minutes)
            return 80 + ((minutes - 30) / 90) * 20
        elif minutes <= self.THRESHOLDS['max_time_minutes']:
            # Acceptable but long
            return 80
        else:
            # Too much time (diminishing returns, might indicate confusion)
            return 70
    
    def _score_documents(self, metrics: Dict) -> float:
        """Score based on documents analyzed"""
        docs = metrics.get('documents_analyzed', 0)
        
        if docs == 0:
            return 30.0  # Penalty for no document analysis
        elif docs < self.THRESHOLDS['min_documents']:
            return 50.0
        elif docs < self.THRESHOLDS['ideal_documents']:
            return 50 + (docs / self.THRESHOLDS['ideal_documents']) * 50
        else:
            return 100.0
    
    def _generate_tips(
        self,
        completeness: float,
        depth: float,
        breadth: float,
        time: float,
        documents: float,
        metrics: Dict
    ) -> List[str]:
        """Generate actionable improvement tips"""
        tips = []
        
        if completeness < 70:
            unanswered = metrics['questions_total'] - metrics['questions_answered']
            tips.append(f"Complete {unanswered} more checklist questions for better coverage")
        
        if depth < 60:
            tips.append("Add more detail to your answers - aim for at least 2-3 sentences per question")
        
        if breadth < 50:
            missing = []
            if not metrics.get('had_financial_analysis'):
                missing.append('financial analysis')
            if not metrics.get('had_competitive_analysis'):
                missing.append('competitive analysis')
            if not metrics.get('had_management_review'):
                missing.append('management review')
            if missing:
                tips.append(f"Consider adding: {', '.join(missing)}")
        
        if documents < 50:
            tips.append("Analyze more source documents (annual reports, earnings calls, etc.)")
        
        if time < 60:
            tips.append("Spend more time on research - thorough analysis typically takes 1-2 hours")
        
        return tips[:3]  # Max 3 tips
    
    def _score_to_grade(self, score: float) -> str:
        """Convert numeric score to letter grade"""
        if score >= 90:
            return 'A'
        elif score >= 80:
            return 'B'
        elif score >= 70:
            return 'C'
        elif score >= 60:
            return 'D'
        else:
            return 'F'
    
    def _get_user_average(self, user_id: Optional[int]) -> float:
        """Get user's historical average score"""
        if not user_id:
            return 70.0  # Default average
        
        from app.models import ResearchOutcome
        
        outcomes = ResearchOutcome.query.filter_by(user_id=user_id).all()
        if not outcomes:
            return 70.0
        
        scores = [o.research_quality_score for o in outcomes if o.research_quality_score]
        return sum(scores) / len(scores) if scores else 70.0


# Convenience function
def calculate_research_quality(
    research_session_id: Optional[int] = None,
    research_project_id: Optional[int] = None,
    metrics: Optional[Dict] = None
) -> ResearchQualityScore:
    """Calculate research quality score"""
    calculator = ResearchQualityCalculator()
    return calculator.calculate_score(
        research_session_id=research_session_id,
        research_project_id=research_project_id,
        metrics=metrics
    )
```

---

# WEEK 3-4: Data Pipeline & Outcome Tracking: THIS IS COMPLETE

## Goals
- [ ] Auto-capture research metrics at decision time
- [ ] Track outcomes when positions close
- [ ] Build correlation analysis
- [ ] Create research effectiveness dashboard

## Research Outcome Pipeline

```python
# app/services/outcome_tracking.py
"""
Outcome Tracking Pipeline
Links research → decisions → portfolio outcomes
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from sqlalchemy import func
import logging

from app import db
from app.models import (
    ResearchProject, ChecklistAnalysis, DecisionJournal,
    Transaction, PortfolioPosition, DestinationCheckpoint
)
from app.models.ai_models import ResearchOutcome  # New model
from .research_quality import calculate_research_quality

logger = logging.getLogger(__name__)


class OutcomeTracker:
    """
    Tracks and correlates research quality with investment outcomes
    """
    
    def create_outcome_record(
        self,
        user_id: int,
        company_id: int,
        decision_journal_id: int,
        transaction: Transaction
    ) -> ResearchOutcome:
        """
        Create outcome record when user makes a BUY transaction
        Called automatically from portfolio transaction flow
        """
        
        # Find linked research
        research_session = None
        research_project = None
        
        journal = DecisionJournal.query.get(decision_journal_id)
        if journal:
            if journal.linked_research_id:
                research_project = ResearchProject.query.get(journal.linked_research_id)
            # Also check for checklist-based research
            research_session = ChecklistAnalysis.query.filter_by(
                user_id=user_id,
                company_id=company_id,
                status='completed'
            ).order_by(ChecklistAnalysis.created_at.desc()).first()
        
        # Calculate research quality
        quality_score = None
        research_metrics = {}
        
        if research_project:
            quality = calculate_research_quality(research_project_id=research_project.id)
            quality_score = quality.overall_score
            research_metrics = {
                'completeness': quality.completeness_score,
                'depth': quality.depth_score,
                'breadth': quality.breadth_score
            }
        elif research_session:
            quality = calculate_research_quality(research_session_id=research_session.id)
            quality_score = quality.overall_score
        
        # Create outcome record
        outcome = ResearchOutcome(
            user_id=user_id,
            company_id=company_id,
            research_session_id=research_session.id if research_session else None,
            research_project_id=research_project.id if research_project else None,
            decision_journal_id=decision_journal_id,
            
            # Research metrics
            research_quality_score=quality_score,
            questions_answered=research_metrics.get('questions_answered', 0),
            documents_analyzed=research_metrics.get('documents_analyzed', 0),
            
            # Decision metrics
            decision_date=transaction.transaction_date,
            entry_price=transaction.price_per_share,
            position_size=transaction.total_value,
            initial_thesis=journal.investment_thesis if journal else None,
            confidence_at_entry=journal.confidence_level if journal else None,
            
            created_at=datetime.utcnow()
        )
        
        db.session.add(outcome)
        db.session.commit()
        
        logger.info(f"Created outcome record {outcome.id} for company {company_id}")
        return outcome
    
    def update_outcome_on_sell(
        self,
        user_id: int,
        company_id: int,
        sell_transaction: Transaction,
        realized_return_pct: float
    ):
        """
        Update outcome record when user sells a position
        """
        outcome = ResearchOutcome.query.filter_by(
            user_id=user_id,
            company_id=company_id,
            exit_date=None  # Not yet closed
        ).order_by(ResearchOutcome.decision_date.desc()).first()
        
        if not outcome:
            logger.warning(f"No outcome record found for company {company_id}")
            return
        
        # Calculate thesis accuracy
        thesis_accuracy = self._calculate_thesis_accuracy(outcome, realized_return_pct)
        
        # Get checkpoint metrics
        checkpoints = DestinationCheckpoint.query.filter_by(
            company_id=company_id,
            user_id=user_id
        ).all()
        
        met_checkpoints = len([c for c in checkpoints if c.status == 'met'])
        
        # Categorize outcome
        outcome_category = self._categorize_outcome(realized_return_pct)
        
        # Update record
        outcome.exit_date = sell_transaction.transaction_date
        outcome.exit_price = sell_transaction.price_per_share
        outcome.realized_return_pct = realized_return_pct
        outcome.actual_hold_days = (
            sell_transaction.transaction_date - outcome.decision_date
        ).days if outcome.decision_date else None
        
        outcome.thesis_accuracy_score = thesis_accuracy
        outcome.checkpoints_met = met_checkpoints
        outcome.checkpoints_total = len(checkpoints)
        
        outcome.outcome_category = outcome_category
        outcome.outcome_recorded_at = datetime.utcnow()
        
        db.session.commit()
        
        # Trigger correlation analysis
        self._analyze_correlations(user_id)
        
        logger.info(f"Updated outcome {outcome.id}: {outcome_category} ({realized_return_pct:.1f}%)")
    
    def _calculate_thesis_accuracy(
        self,
        outcome: ResearchOutcome,
        realized_return: float
    ) -> float:
        """
        Calculate how accurate the initial thesis was
        Based on: expected return vs actual, checkpoint hit rate, thesis validity
        """
        scores = []
        
        # Return expectation accuracy
        if outcome.expected_return_pct:
            expected = outcome.expected_return_pct
            actual = realized_return
            
            # If both positive or both negative, partial credit
            if (expected > 0 and actual > 0) or (expected < 0 and actual < 0):
                # Score based on how close
                diff = abs(expected - actual)
                accuracy = max(0, 100 - diff * 2)  # -2 points per % difference
                scores.append(accuracy)
            else:
                # Wrong direction
                scores.append(20)
        
        # Hold period accuracy
        if outcome.expected_hold_months and outcome.actual_hold_days:
            expected_days = outcome.expected_hold_months * 30
            actual_days = outcome.actual_hold_days
            
            ratio = min(expected_days, actual_days) / max(expected_days, actual_days)
            scores.append(ratio * 100)
        
        # Checkpoint accuracy
        if outcome.checkpoints_total and outcome.checkpoints_total > 0:
            checkpoint_pct = outcome.checkpoints_met / outcome.checkpoints_total
            scores.append(checkpoint_pct * 100)
        
        return sum(scores) / len(scores) if scores else 50.0
    
    def _categorize_outcome(self, return_pct: float) -> str:
        """Categorize outcome for analysis"""
        if return_pct >= 25:
            return 'big_win'
        elif return_pct >= 5:
            return 'small_win'
        elif return_pct >= -5:
            return 'break_even'
        elif return_pct >= -25:
            return 'small_loss'
        else:
            return 'big_loss'
    
    def _analyze_correlations(self, user_id: int):
        """
        Analyze correlations between research quality and outcomes
        Runs after each position close
        """
        outcomes = ResearchOutcome.query.filter(
            ResearchOutcome.user_id == user_id,
            ResearchOutcome.realized_return_pct.isnot(None)
        ).all()
        
        if len(outcomes) < 5:
            # Not enough data for meaningful correlation
            return
        
        # Group by research quality
        high_quality = [o for o in outcomes if (o.research_quality_score or 0) >= 70]
        low_quality = [o for o in outcomes if (o.research_quality_score or 0) < 70]
        
        if high_quality and low_quality:
            high_avg = sum(o.realized_return_pct for o in high_quality) / len(high_quality)
            low_avg = sum(o.realized_return_pct for o in low_quality) / len(low_quality)
            
            # Store insight about correlation
            from app.services.ai_providers.unified_ai_service import get_ai_service
            
            if high_avg > low_avg + 5:  # Meaningful difference
                get_ai_service().generate_insight(
                    insight_type='pattern',
                    context={
                        'pattern': 'research_quality_correlation',
                        'high_quality_avg_return': high_avg,
                        'low_quality_avg_return': low_avg,
                        'difference': high_avg - low_avg,
                        'sample_size': len(outcomes)
                    },
                    user_history={}
                )


# Integration with portfolio transactions
def on_buy_transaction(transaction: Transaction, decision_journal: DecisionJournal):
    """Hook called when user makes a buy transaction"""
    tracker = OutcomeTracker()
    tracker.create_outcome_record(
        user_id=transaction.user_id,
        company_id=transaction.company_id,
        decision_journal_id=decision_journal.id,
        transaction=transaction
    )


def on_sell_transaction(transaction: Transaction, realized_return_pct: float):
    """Hook called when user makes a sell transaction"""
    tracker = OutcomeTracker()
    tracker.update_outcome_on_sell(
        user_id=transaction.user_id,
        company_id=transaction.company_id,
        sell_transaction=transaction,
        realized_return_pct=realized_return_pct
    )
```

---

# WEEK 7-8: Intelligence Engine (Phase 2)

## Goals
- [ ] Real-time warnings during research
- [ ] Pattern-based suggestions
- [ ] Similar situation matching
- [ ] Warning UI integration

## Warning Generation System

```python
# app/services/intelligence_engine.py
"""
Intelligence Engine
Generates warnings and insights during research
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging

from app import db
from app.models import (
    Company, MistakeLog, ResearchProject,
    ChecklistAnalysis, DecisionJournal
)
from app.models.ai_models import ResearchOutcome, AIInsight, EmbeddingStore
from app.services.ai_providers.unified_ai_service import get_ai_service

logger = logging.getLogger(__name__)


class IntelligenceEngine:
    """
    Generates contextual warnings and insights
    The "magic" users will feel - proactive AI assistance
    """
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.ai_service = get_ai_service()
    
    def analyze_research_context(
        self,
        company_id: int,
        current_thesis: Optional[str] = None,
        research_session_id: Optional[int] = None,
        research_project_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Main entry point: analyze current research and generate relevant warnings
        
        Called when:
        - User starts researching a company
        - User is about to make a buy decision
        - Periodically during long research sessions
        
        Returns list of warnings/insights to show user
        """
        warnings = []
        
        company = Company.query.get(company_id)
        if not company:
            return warnings
        
        # 1. Check for similar past mistakes
        similar_mistakes = self._find_similar_mistakes(company, current_thesis)
        if similar_mistakes:
            warnings.append(self._create_mistake_warning(company, similar_mistakes))
        
        # 2. Check for patterns in user's history
        patterns = self._detect_relevant_patterns(company)
        for pattern in patterns:
            warnings.append(self._create_pattern_warning(company, pattern))
        
        # 3. Check for similar companies in portfolio
        portfolio_conflicts = self._check_portfolio_conflicts(company)
        if portfolio_conflicts:
            warnings.append(self._create_portfolio_warning(company, portfolio_conflicts))
        
        # 4. Check sector-specific concerns
        sector_insights = self._analyze_sector_performance(company)
        if sector_insights:
            warnings.append(sector_insights)
        
        # 5. If thesis provided, analyze it
        if current_thesis:
            thesis_analysis = self._analyze_thesis_quality(company, current_thesis)
            if thesis_analysis.get('risk_flags'):
                warnings.append(self._create_thesis_warning(company, thesis_analysis))
        
        # Store generated insights for tracking
        for warning in warnings:
            self._store_insight(warning, company_id)
        
        return warnings
    
    def _find_similar_mistakes(
        self,
        company: Company,
        thesis: Optional[str]
    ) -> List[MistakeLog]:
        """Find past mistakes similar to current situation"""
        
        # Get user's past mistakes
        mistakes = MistakeLog.query.filter_by(user_id=self.user_id).all()
        
        if not mistakes:
            return []
        
        similar = []
        
        for mistake in mistakes:
            similarity_score = 0
            
            # Check sector match
            if company.sector and mistake.sector == company.sector:
                similarity_score += 30
            
            # Check industry match
            if company.industry and mistake.industry == company.industry:
                similarity_score += 20
            
            # If we have thesis, check semantic similarity
            if thesis and mistake.description:
                # Use embedding similarity
                thesis_embedding = self.ai_service._generate_embedding(thesis)
                mistake_embedding = self._get_or_create_embedding(
                    'mistake', mistake.id, mistake.description
                )
                
                if mistake_embedding:
                    cosine_sim = self._cosine_similarity(thesis_embedding, mistake_embedding)
                    similarity_score += cosine_sim * 50
            
            if similarity_score > 40:
                similar.append({
                    'mistake': mistake,
                    'similarity': similarity_score
                })
        
        # Sort by similarity
        similar.sort(key=lambda x: x['similarity'], reverse=True)
        return [s['mistake'] for s in similar[:3]]  # Top 3
    
    def _detect_relevant_patterns(self, company: Company) -> List[Dict]:
        """Detect behavioral patterns relevant to this company"""
        
        patterns = []
        
        # Get user's research outcomes
        outcomes = ResearchOutcome.query.filter(
            ResearchOutcome.user_id == self.user_id,
            ResearchOutcome.realized_return_pct.isnot(None)
        ).all()
        
        if len(outcomes) < 5:
            return patterns
        
        # Pattern 1: Sector underperformance
        sector_outcomes = [o for o in outcomes if o.company.sector == company.sector]
        if len(sector_outcomes) >= 3:
            sector_avg = sum(o.realized_return_pct for o in sector_outcomes) / len(sector_outcomes)
            overall_avg = sum(o.realized_return_pct for o in outcomes) / len(outcomes)
            
            if sector_avg < overall_avg - 10:
                patterns.append({
                    'type': 'sector_underperformance',
                    'severity': 'medium',
                    'data': {
                        'sector': company.sector,
                        'sector_avg_return': sector_avg,
                        'overall_avg_return': overall_avg,
                        'difference': sector_avg - overall_avg
                    }
                })
        
        # Pattern 2: Low research quality → bad outcomes
        low_quality_outcomes = [
            o for o in outcomes 
            if (o.research_quality_score or 0) < 60
        ]
        if len(low_quality_outcomes) >= 3:
            low_quality_avg = sum(o.realized_return_pct for o in low_quality_outcomes) / len(low_quality_outcomes)
            high_quality_outcomes = [o for o in outcomes if (o.research_quality_score or 0) >= 70]
            
            if high_quality_outcomes:
                high_quality_avg = sum(o.realized_return_pct for o in high_quality_outcomes) / len(high_quality_outcomes)
                
                if low_quality_avg < high_quality_avg - 5:
                    patterns.append({
                        'type': 'research_quality_matters',
                        'severity': 'high',
                        'data': {
                            'low_quality_avg': low_quality_avg,
                            'high_quality_avg': high_quality_avg,
                            'difference': high_quality_avg - low_quality_avg
                        }
                    })
        
        # Pattern 3: Disposition effect (holding losers too long)
        winners = [o for o in outcomes if o.realized_return_pct > 0]
        losers = [o for o in outcomes if o.realized_return_pct < 0]
        
        if len(winners) >= 3 and len(losers) >= 3:
            avg_winner_hold = sum(o.actual_hold_days or 0 for o in winners) / len(winners)
            avg_loser_hold = sum(o.actual_hold_days or 0 for o in losers) / len(losers)
            
            if avg_loser_hold > avg_winner_hold * 1.5:
                patterns.append({
                    'type': 'disposition_effect',
                    'severity': 'medium',
                    'data': {
                        'avg_winner_hold_days': avg_winner_hold,
                        'avg_loser_hold_days': avg_loser_hold,
                        'ratio': avg_loser_hold / avg_winner_hold
                    }
                })
        
        return patterns
    
    def _check_portfolio_conflicts(self, company: Company) -> List[Dict]:
        """Check for conflicts with existing portfolio positions"""
        
        from app.models import PortfolioPosition
        
        positions = PortfolioPosition.query.filter(
            PortfolioPosition.user_id == self.user_id,
            PortfolioPosition.shares > 0
        ).all()
        
        conflicts = []
        
        for position in positions:
            # Check for same sector concentration
            if position.company.sector == company.sector:
                # Count sector positions
                sector_positions = [
                    p for p in positions 
                    if p.company.sector == company.sector
                ]
                
                if len(sector_positions) >= 3:
                    conflicts.append({
                        'type': 'sector_concentration',
                        'existing_companies': [p.company.name for p in sector_positions],
                        'sector': company.sector
                    })
                    break
            
            # Check for thesis contradiction (using embeddings)
            if position.company.id != company.id:
                # Get decision journals
                journal = DecisionJournal.query.filter_by(
                    company_id=position.company.id,
                    user_id=self.user_id
                ).first()
                
                if journal and journal.investment_thesis:
                    # Check if theses might conflict
                    # (e.g., one bullish on rates, one bearish)
                    # This would use more sophisticated NLP in production
                    pass
        
        return conflicts
    
    def _analyze_sector_performance(self, company: Company) -> Optional[Dict]:
        """Analyze user's performance in this sector"""
        
        if not company.sector:
            return None
        
        outcomes = ResearchOutcome.query.filter(
            ResearchOutcome.user_id == self.user_id,
            ResearchOutcome.realized_return_pct.isnot(None)
        ).join(Company).filter(
            Company.sector == company.sector
        ).all()
        
        if len(outcomes) < 3:
            return None
        
        avg_return = sum(o.realized_return_pct for o in outcomes) / len(outcomes)
        win_rate = len([o for o in outcomes if o.realized_return_pct > 0]) / len(outcomes)
        
        if avg_return < -5 or win_rate < 0.4:
            return {
                'type': 'warning',
                'title': f'Sector Performance Alert: {company.sector}',
                'insight_text': f"Your past investments in {company.sector} have averaged {avg_return:.1f}% return with a {win_rate:.0%} win rate. Consider extra due diligence.",
                'severity': 'medium',
                'supporting_data': {
                    'sector': company.sector,
                    'avg_return': avg_return,
                    'win_rate': win_rate,
                    'sample_size': len(outcomes)
                }
            }
        
        return None
    
    def _analyze_thesis_quality(
        self,
        company: Company,
        thesis: str
    ) -> Dict[str, Any]:
        """Use Claude to analyze thesis quality"""
        
        # Get historical context
        historical = self._get_historical_context(company)
        
        research_data = {
            'questions_answered': 0,
            'questions_total': 0,
            'key_findings': '',
            'identified_risks': ''
        }
        
        return self.ai_service.analyze_thesis(
            company_name=company.name,
            thesis_text=thesis,
            research_data=research_data,
            historical_context=historical
        )
    
    def _get_historical_context(self, company: Company) -> Dict[str, Any]:
        """Gather historical context for AI analysis"""
        
        # Find similar companies user has researched
        similar_companies = self.ai_service.find_similar_situations(
            f"{company.name} {company.sector} {company.industry}",
            self.user_id,
            top_k=3
        )
        
        # Get sector mistakes
        sector_mistakes = MistakeLog.query.filter_by(
            user_id=self.user_id,
            sector=company.sector
        ).limit(3).all()
        
        # Get user's common blind spots
        all_mistakes = MistakeLog.query.filter_by(user_id=self.user_id).all()
        # Count mistake types
        mistake_types = {}
        for m in all_mistakes:
            t = m.mistake_type or 'unknown'
            mistake_types[t] = mistake_types.get(t, 0) + 1
        
        common_mistakes = sorted(mistake_types.items(), key=lambda x: x[1], reverse=True)[:3]
        
        return {
            'similar_companies': [s['text'][:100] for s in similar_companies],
            'sector_mistakes': [m.title for m in sector_mistakes],
            'blind_spots': [m[0] for m in common_mistakes]
        }
    
    def _create_mistake_warning(
        self,
        company: Company,
        similar_mistakes: List[MistakeLog]
    ) -> Dict[str, Any]:
        """Create warning based on similar past mistakes"""
        
        mistake_summaries = [
            f"• {m.title}: Lost ${m.cost_estimate or 0:,.0f}"
            for m in similar_mistakes[:2]
        ]
        
        return {
            'type': 'warning',
            'title': 'Similar to Past Mistakes',
            'insight_text': f"This investment shares characteristics with companies where you've had losses:\n\n" + "\n".join(mistake_summaries),
            'severity': 'high',
            'supporting_data': {
                'mistake_ids': [m.id for m in similar_mistakes],
                'total_past_cost': sum(m.cost_estimate or 0 for m in similar_mistakes)
            },
            'suggested_action': 'Review your past mistakes and ensure you\'ve addressed those factors in your current research.'
        }
    
    def _create_pattern_warning(
        self,
        company: Company,
        pattern: Dict
    ) -> Dict[str, Any]:
        """Create warning based on detected pattern"""
        
        # Get Claude to explain the pattern
        explanation = self.ai_service.claude.explain_pattern(
            pattern['type'],
            pattern['data'],
            {'user_id': self.user_id}
        ) if self.ai_service.claude.is_available() else ""
        
        titles = {
            'sector_underperformance': f"You've Underperformed in {company.sector}",
            'research_quality_matters': 'Research Quality Alert',
            'disposition_effect': 'Behavioral Pattern Detected'
        }
        
        return {
            'type': 'pattern',
            'title': titles.get(pattern['type'], 'Pattern Detected'),
            'insight_text': explanation or f"Pattern detected: {pattern['type']}",
            'severity': pattern['severity'],
            'supporting_data': pattern['data'],
            'suggested_action': self._get_pattern_action(pattern['type'])
        }
    
    def _create_portfolio_warning(
        self,
        company: Company,
        conflicts: List[Dict]
    ) -> Dict[str, Any]:
        """Create warning about portfolio conflicts"""
        
        if conflicts[0]['type'] == 'sector_concentration':
            existing = ', '.join(conflicts[0]['existing_companies'][:3])
            return {
                'type': 'warning',
                'title': f'Portfolio Concentration: {company.sector}',
                'insight_text': f"You already have {len(conflicts[0]['existing_companies'])} positions in {company.sector}: {existing}. Adding {company.name} may over-concentrate your portfolio.",
                'severity': 'medium',
                'supporting_data': conflicts[0],
                'suggested_action': 'Consider if you want this much exposure to one sector.'
            }
        
        return {}
    
    def _create_thesis_warning(
        self,
        company: Company,
        thesis_analysis: Dict
    ) -> Dict[str, Any]:
        """Create warning based on thesis analysis"""
        
        flags = thesis_analysis.get('risk_flags', [])
        weaknesses = thesis_analysis.get('weaknesses', [])
        
        return {
            'type': 'suggestion',
            'title': 'Thesis Review Suggestions',
            'insight_text': thesis_analysis.get('quality_assessment', ''),
            'severity': 'low' if len(flags) == 0 else 'medium',
            'supporting_data': {
                'risk_flags': flags,
                'weaknesses': weaknesses,
                'suggested_questions': thesis_analysis.get('suggested_questions', [])
            },
            'suggested_action': 'Consider addressing the identified weaknesses before investing.'
        }
    
    def _get_pattern_action(self, pattern_type: str) -> str:
        """Get suggested action for pattern type"""
        actions = {
            'sector_underperformance': 'Consider whether you have an edge in this sector, or if you should focus elsewhere.',
            'research_quality_matters': 'Your high-quality research has outperformed. Take extra time on this one.',
            'disposition_effect': 'Set a clear exit strategy before investing, including stop-loss levels.'
        }
        return actions.get(pattern_type, 'Review this pattern and adjust your approach.')
    
    def _store_insight(self, warning: Dict, company_id: int):
        """Store generated insight for tracking and learning"""
        
        insight = AIInsight(
            user_id=self.user_id,
            insight_type=warning.get('type', 'warning'),
            trigger_type='research_analysis',
            context_type='company',
            context_id=company_id,
            company_id=company_id,
            
            title=warning.get('title', ''),
            insight_text=warning.get('insight_text', ''),
            supporting_data=warning.get('supporting_data'),
            
            ai_provider='hybrid',
            confidence=0.8,
            
            created_at=datetime.utcnow()
        )
        
        db.session.add(insight)
        db.session.commit()
    
    def _get_or_create_embedding(
        self,
        entity_type: str,
        entity_id: int,
        text: str
    ) -> Optional[List[float]]:
        """Get or create embedding for entity"""
        
        # Check if exists
        existing = EmbeddingStore.query.filter_by(
            user_id=self.user_id,
            entity_type=entity_type,
            entity_id=entity_id
        ).first()
        
        if existing:
            return existing.embedding_vector
        
        # Create new embedding
        embedding = self.ai_service._generate_embedding(text)
        
        store = EmbeddingStore(
            user_id=self.user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            embedding_vector=embedding,
            source_text=text[:1000],
            embedding_model='all-MiniLM-L6-v2'
        )
        
        db.session.add(store)
        db.session.commit()
        
        return embedding
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        import numpy as np
        a = np.array(a)
        b = np.array(b)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


# Convenience function
def get_research_warnings(
    user_id: int,
    company_id: int,
    thesis: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Get warnings for current research context"""
    engine = IntelligenceEngine(user_id)
    return engine.analyze_research_context(company_id, thesis)
```

---


# WEEK 5-6: Portfolio Intelligence — Full Plan

### The Big Picture

We've built the **data collection layer** (ResearchOutcome tracks quality→results). Now we **visualize and act on it**.

```
┌─────────────────────────────────────────────────────────────────┐
│                    PORTFOLIO INTELLIGENCE                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │ Correlation  │    │ Checkpoint   │    │  Position    │      │
│  │  Dashboard   │    │  Reminders   │    │  Monitoring  │      │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘      │
│         │                   │                   │               │
│         ▼                   ▼                   ▼               │
│  "High quality         "AAPL earnings      "Your NVDA thesis   │
│   research = 12%       call in 3 days"      was 'AI growth'    │
│   better returns"                           but it's down 20%" │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  Learning Insights                       │   │
│  │  "Your best trades: 80+ quality score, held 6+ months"  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

### Step 1: Correlation Dashboard

**What it shows:**
- Research quality score vs actual returns (scatter plot)
- Average return by quality grade (A, B, C, D, F)
- "Research Advantage" metric (researched vs non-researched returns)

**Data source:** `ResearchOutcome` table (we built this!)

**Location:** New page at `/portfolio/analytics/research-correlation` or widget on existing analytics page

**Example output:**
```
┌─────────────────────────────────────────────────┐
│  📊 Research Quality → Returns Correlation      │
├─────────────────────────────────────────────────┤
│                                                 │
│  Grade A (90+):  +18.5% avg return  ████████▓  │
│  Grade B (80-89): +12.2% avg return ██████▓    │
│  Grade C (70-79): +5.1% avg return  ███▓       │
│  Grade D (60-69): -2.3% avg return  ▓          │
│  Grade F (<60):   -8.7% avg return  ░░░        │
│                                                 │
│  🎯 Your Research Advantage: +15.3%            │
│  (Researched positions outperform by 15.3%)    │
│                                                 │
└─────────────────────────────────────────────────┘
```

---

### Step 2: Checkpoint Reminders

**What it does:**
- Queries `DestinationCheckpoint` for upcoming dates
- Shows on dashboard and/or sends notifications
- Prompts user to evaluate: "Did this checkpoint get met?"

**Data source:** `DestinationCheckpoint` table (already exists)

**Location:** Widget on portfolio dashboard, notification system

**Example output:**
```
┌─────────────────────────────────────────────────┐
│  📅 Upcoming Checkpoints                        │
├─────────────────────────────────────────────────┤
│                                                 │
│  🔴 OVERDUE (2 days ago)                        │
│     AAPL: "Q4 earnings beat estimates"          │
│     [Mark Met] [Mark Not Met] [Snooze]          │
│                                                 │
│  🟡 THIS WEEK                                   │
│     NVDA: "Data center revenue > $10B"          │
│     Target: Dec 30, 2025                        │
│                                                 │
│  🟢 NEXT 30 DAYS                                │
│     MSFT: "Azure growth > 25%"                  │
│     Target: Jan 15, 2026                        │
│                                                 │
└─────────────────────────────────────────────────┘
```

---

### Step 3: Position Monitoring (Thesis vs Reality)

**What it does:**
- Compares original investment thesis to current performance
- Flags positions where reality diverges from thesis
- Prompts reflection: "Is your thesis still valid?"

**Data source:** `DecisionJournal.investment_thesis`, `PortfolioPosition`, current prices

**Example output:**
```
┌─────────────────────────────────────────────────┐
│  ⚠️ Thesis Reality Check                        │
├─────────────────────────────────────────────────┤
│                                                 │
│  NVDA — NEEDS ATTENTION                         │
│  ├─ Original thesis: "AI demand drives 50%     │
│  │   revenue growth"                            │
│  ├─ Expected: +40% in 12 months                │
│  ├─ Actual: -15% (held 8 months)               │
│  └─ [Review Thesis] [Update] [Sell?]           │
│                                                 │
│  AAPL — ON TRACK                                │
│  ├─ Original thesis: "Services revenue growth" │
│  ├─ Expected: +20% in 18 months                │
│  ├─ Actual: +12% (held 6 months)               │
│  └─ Tracking well ✓                            │
│                                                 │
└─────────────────────────────────────────────────┘
```

---

### Step 4: Learning Insights

**What it does:**
- Analyzes completed `ResearchOutcome` records
- Finds patterns in winning vs losing trades
- Generates personalized insights

**Data source:** `ResearchOutcome`, `DecisionJournal`, `PortfolioPosition`

**Example output:**
```
┌─────────────────────────────────────────────────┐
│  💡 What Your Data Tells You                    │
├─────────────────────────────────────────────────┤
│                                                 │
│  ✅ WINNING PATTERNS                            │
│  • Your best trades had quality scores 80+     │
│  • You perform better holding 6+ months        │
│  • Tech sector: 72% win rate                   │
│                                                 │
│  ⚠️ WATCH OUT FOR                               │
│  • Trades without research: -8% avg return     │
│  • Positions sold < 30 days: 65% were losses   │
│  • High confidence (9-10) ≠ better results     │
│                                                 │
│  📈 YOUR EDGE                                   │
│  Research quality is your strongest predictor  │
│  of success. Keep investing in thorough        │
│  analysis!                                      │
│                                                 │
└─────────────────────────────────────────────────┘
```

---

## 📁 Files We'll Create

| Step | Files |
|------|-------|
| **1** | `app/services/portfolio_intelligence.py` (service) |
| | `app/portfolio/templates/research_correlation.html` (UI) |
| **2** | Add to service + dashboard widget |
| **3** | Add to service + new template section |
| **4** | Add to service + insights card |

---




# Summary: Complete Implementation Map

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    COMPLETE IMPLEMENTATION ROADMAP                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  WEEK 1-2: FOUNDATION                                                       │
│  ├── Database: research_outcome, ai_insight, embedding_store tables         │
│  ├── Claude API: claude_provider.py integration                             │
│  ├── Hybrid Service: unified_ai_service.py routing                          │
│  └── Quality Scoring: research_quality.py calculator                        │
│      │                                                                      │
│      └── ENABLES: "Research Quality Score: 73/100"                          │
│                                                                             │
│  WEEK 3-4: DATA PIPELINE                                                    │
│  ├── Outcome Tracking: outcome_tracking.py pipeline                         │
│  ├── Transaction Hooks: on_buy_transaction, on_sell_transaction             │
│  ├── Correlation Analysis: research ↔ returns                               │
│  └── Dashboard Widget: Research Effectiveness                               │
│      │                                                                      │
│      └── ENABLES: "Your researched investments return 15% more"             │
│                                                                             │
│  WEEK 5-6: INTELLIGENCE ENGINE                                              │
│  ├── Warning Generation: intelligence_engine.py                             │
│  ├── Pattern Detection: behavioral bias ML models                           │
│  ├── Similarity Matching: embedding-based search                            │
│  └── UI Integration: Warning components in research flow                    │
│      │                                                                      │
│      └── ENABLES: "Warning: Similar to past mistake with XYZ Corp"          │
│                                                                             │
│  WEEK 7-8: PORTFOLIO INTELLIGENCE                                           │
│  ├── Thesis Health Score: multi-factor calculation                          │
│  ├── Position Reviews: automated quarterly analysis                         │
│  ├── Checkpoint Monitoring: thesis validation alerts                        │
│  └── Learning Dashboard: comprehensive analytics                            │
│      │                                                                      │
│      └── ENABLES: "Thesis Health: 65% - 2 checkpoints at risk"              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```




# Tuning tips 

 1. Research Quality Calculator (app/services/research_quality.py)
  - 5-factor scoring algorithm (0-100 scale):
    - Completeness (25%): % of questions answered
    - Depth (25%): Answer quality/length
    - Breadth (20%): Analysis variety (financial, competitive, management, valuation)
    - Time (15%): Time invested (30-120 min optimal)
    - Documents (15%): Document analysis depth
  - Returns ResearchQualityScore dataclass with grade (A-F) and improvement tips

  2. Outcome Tracker (app/services/outcome_tracking.py)
  - BUY Hook: Creates ResearchOutcome record linking research quality to investment
  - SELL Hook: Updates outcome with realized returns, thesis accuracy
  - Thesis Accuracy Algorithm:
    - Return expectation (40%)
    - Hold period accuracy (30%)
    - Checkpoint hit rate (30%)
  - Outcome Categories: big_win (≥25%), small_win (≥5%), break_even, small_loss, big_loss
  - Correlation Analysis: Auto-runs when ≥5 outcomes, generates AIInsight if meaningful patterns found


    How It Works

  When user makes a BUY:
  1. Transaction created → on_buy_transaction() called
  2. Finds linked research (DecisionJournal → ResearchProject → ResearchSession)
  3. Calculates research quality score (0-100)
  4. Creates ResearchOutcome record with all metrics
  5. Tracks: quality score, questions answered, documents, thesis, confidence, expected return

  When user makes a SELL:
  1. Transaction created → on_sell_transaction() called
  2. Finds open ResearchOutcome for this company
  3. Calculates realized return %
  4. Updates: exit price, return %, hold days, outcome category, thesis accuracy
  5. Runs correlation analysis if ≥5 outcomes exist
  6. Generates AIInsight if research quality correlates with returns (>5% difference)

  Example AIInsight Generated:
  "Your high-quality research (score 70+) has averaged 18.5% returns, while lower-quality research averaged 6.2% returns. That's a 12.3% difference! This suggests your thorough research pays off."


  ## Next testing phase 

    When you're ready to test:
  1. Run python test_outcome_tracking.py to verify everything works
  2. Make real BUY transactions in the app (with or without research)
  3. Verify ResearchOutcome records appear in database
  4. Make SELL transactions to complete the cycle
  5. Check AIInsight table after 5+ completed outcomes