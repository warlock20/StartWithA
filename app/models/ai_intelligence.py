# app/models/ai_intelligence.py
"""
AI Intelligence Models for Investment Research Platform
Created as part of Week 1-2 Foundation Layer
"""

from app import db
from app.utils.time_utils import now_utc
from sqlalchemy.dialects.postgresql import JSON, ARRAY
from pgvector.sqlalchemy import Vector


class ResearchOutcome(db.Model):
    """
    Links research quality to investment results.
    This is the CORE table for Phase 1: Research-to-Results Feedback Loop
    """
    __tablename__ = 'research_outcome'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)

    # Link to research (one of these will be set)
    checklist_analysis_id = db.Column(db.Integer, db.ForeignKey('checklist_analysis.id', ondelete='SET NULL'), nullable=True)
    project_id = db.Column(db.Integer, db.ForeignKey('research_project.id', ondelete='SET NULL'), nullable=True)

    # Link to decision and portfolio
    decision_journal_id = db.Column(db.Integer, db.ForeignKey('decision_journal.id', ondelete='SET NULL'), nullable=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id', ondelete='CASCADE'), nullable=False, index=True)

    # ===== RESEARCH METRICS (captured at decision time) =====
    research_quality_score = db.Column(db.Float, nullable=True)  # 0-100 composite score
    questions_answered = db.Column(db.Integer, default=0)
    questions_total = db.Column(db.Integer, default=0)
    documents_analyzed = db.Column(db.Integer, default=0)
    ai_assists_used = db.Column(db.Integer, default=0)
    research_duration_minutes = db.Column(db.Integer, default=0)
    checklist_completion_pct = db.Column(db.Float, default=0)

    # Research depth indicators
    had_financial_analysis = db.Column(db.Boolean, default=False)
    had_competitive_analysis = db.Column(db.Boolean, default=False)
    had_management_review = db.Column(db.Boolean, default=False)
    had_valuation_model = db.Column(db.Boolean, default=False)

    # ===== DECISION METRICS (captured at buy) =====
    decision_date = db.Column(db.Date, nullable=True, index=True)
    entry_price = db.Column(db.Numeric(15, 4), nullable=True)
    position_size = db.Column(db.Numeric(15, 2), nullable=True)
    initial_thesis = db.Column(db.Text, nullable=True)
    confidence_at_entry = db.Column(db.Integer, nullable=True)  # 1-10 scale
    expected_return_pct = db.Column(db.Float, nullable=True)
    expected_hold_months = db.Column(db.Integer, nullable=True)

    # ===== OUTCOME METRICS (updated over time) =====
    current_return_pct = db.Column(db.Float, nullable=True)
    exit_date = db.Column(db.Date, nullable=True)
    exit_price = db.Column(db.Numeric(15, 4), nullable=True)
    realized_return_pct = db.Column(db.Float, nullable=True)
    actual_hold_days = db.Column(db.Integer, nullable=True)

    # Thesis accuracy (how well predictions matched reality)
    thesis_accuracy_score = db.Column(db.Float, nullable=True)  # 0-100
    checkpoints_met = db.Column(db.Integer, default=0)
    checkpoints_total = db.Column(db.Integer, default=0)
    thesis_still_valid = db.Column(db.Boolean, default=True)

    # ===== LEARNING METRICS (computed by ML) =====
    outcome_category = db.Column(db.String(20), nullable=True, index=True)  # 'big_win', 'small_win', 'small_loss', 'big_loss'
    predictive_factors = db.Column(JSON, nullable=True)  # Which research factors predicted this outcome
    correlation_confidence = db.Column(db.Float, nullable=True)
    lessons_extracted = db.Column(JSON, nullable=True)  # AI-generated lessons

    # Timestamps
    created_at = db.Column(db.DateTime, default=now_utc)
    outcome_recorded_at = db.Column(db.DateTime, nullable=True)
    last_updated_at = db.Column(db.DateTime, default=now_utc, onupdate=now_utc)

    # Relationships
    user = db.relationship('User', backref=db.backref('research_outcomes', lazy='dynamic'))
    company = db.relationship('Company', backref=db.backref('research_outcomes', lazy='dynamic'))

    def __repr__(self):
        return f'<ResearchOutcome {self.id}: {self.company_id} - {self.outcome_category}>'


class AIInsight(db.Model):
    """
    Stores AI-generated warnings and suggestions.
    Enables learning from user feedback and validation over time.
    """
    __tablename__ = 'ai_insight'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)

    # What triggered this insight
    insight_type = db.Column(db.String(50), nullable=False, index=True)  # 'warning', 'suggestion', 'pattern', 'reminder'
    trigger_type = db.Column(db.String(50), nullable=False)  # 'research_start', 'buy_transaction', 'thesis_review', 'periodic'

    # Context: where does this insight apply?
    context_type = db.Column(db.String(50), nullable=True)  # 'company', 'research', 'portfolio', 'journal'
    context_id = db.Column(db.Integer, nullable=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id', ondelete='SET NULL'), nullable=True)

    # The insight content
    title = db.Column(db.String(200), nullable=False)
    insight_text = db.Column(db.Text, nullable=False)
    supporting_data = db.Column(JSON, nullable=True)  # Evidence/data that supports this insight

    # AI metadata
    ai_provider = db.Column(db.String(50), nullable=True)  # 'claude', 'gemini', 'ml_model'
    model_version = db.Column(db.String(50), nullable=True)
    confidence = db.Column(db.Float, nullable=True)  # 0-1 confidence score
    generation_prompt = db.Column(db.Text, nullable=True)  # For debugging/improvement

    # Related patterns/history
    related_mistake_ids = db.Column(ARRAY(db.Integer), nullable=True)  # Links to mistake_log entries
    related_outcome_ids = db.Column(ARRAY(db.Integer), nullable=True)  # Links to research_outcome entries
    similar_past_insights = db.Column(ARRAY(db.Integer), nullable=True)  # Links to previous similar insights

    # User interaction tracking
    was_shown = db.Column(db.Boolean, default=False)
    shown_at = db.Column(db.DateTime, nullable=True)
    user_action = db.Column(db.String(50), nullable=True)  # 'dismissed', 'acknowledged', 'applied', 'helpful', 'not_helpful'
    user_feedback = db.Column(db.Text, nullable=True)
    action_taken_at = db.Column(db.DateTime, nullable=True)

    # Outcome validation (did the warning prove correct?)
    was_validated = db.Column(db.Boolean, nullable=True, index=True)
    validation_outcome = db.Column(db.String(50), nullable=True, index=True)  # 'correct', 'incorrect', 'partially_correct', 'unknown'
    validated_at = db.Column(db.DateTime, nullable=True)

    # Status
    is_active = db.Column(db.Boolean, default=True, index=True)
    expires_at = db.Column(db.DateTime, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=now_utc, index=True)

    # Relationships
    user = db.relationship('User', backref=db.backref('ai_insights', lazy='dynamic'))
    company = db.relationship('Company', backref=db.backref('ai_insights', lazy='dynamic'))

    def __repr__(self):
        return f'<AIInsight {self.id}: {self.insight_type} - {self.title}>'


class EmbeddingStore(db.Model):
    """
    Stores vector embeddings for similarity matching.
    Enables "similar to past mistake" warnings and pattern detection.
    Requires pgvector extension.
    """
    __tablename__ = 'embedding_store'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)

    # What entity does this embedding represent?
    entity_type = db.Column(db.String(50), nullable=False, index=True)  # 'thesis', 'mistake', 'research_note', 'company_summary'
    entity_id = db.Column(db.Integer, nullable=False, index=True)

    # The embedding vector (384 dimensions for MiniLM, 1536 for OpenAI)
    embedding_vector = db.Column(Vector(384), nullable=True)  # Using sentence-transformers default

    # Source text that was embedded
    source_text = db.Column(db.Text, nullable=True)
    text_hash = db.Column(db.String(64), nullable=True)  # For deduplication

    # Metadata
    embedding_model = db.Column(db.String(100), nullable=False)  # 'all-MiniLM-L6-v2', 'text-embedding-ada-002'
    embedding_version = db.Column(db.Integer, default=1)

    # Timestamps
    created_at = db.Column(db.DateTime, default=now_utc)

    # Relationships
    user = db.relationship('User', backref=db.backref('embeddings', lazy='dynamic'))

    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('user_id', 'entity_type', 'entity_id', 'embedding_model', name='uix_embedding_unique'),
    )

    def __repr__(self):
        return f'<EmbeddingStore {self.id}: {self.entity_type} #{self.entity_id}>'


class MLPredictionLog(db.Model):
    """
    Tracks ML model predictions for validation.
    Enables model improvement over time by comparing predictions to actual outcomes.
    """
    __tablename__ = 'ml_prediction_log'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)

    # Model info
    model_name = db.Column(db.String(100), nullable=False, index=True)  # 'research_quality', 'bias_detector', 'outcome_predictor'
    model_version = db.Column(db.String(50), nullable=False, index=True)

    # Prediction details
    prediction_type = db.Column(db.String(50), nullable=False)  # 'score', 'classification', 'probability'
    input_features = db.Column(JSON, nullable=False)  # Features used for prediction

    # Prediction output
    predicted_value = db.Column(db.Float, nullable=True)
    predicted_label = db.Column(db.String(100), nullable=True)
    prediction_probabilities = db.Column(JSON, nullable=True)  # For multi-class predictions
    confidence = db.Column(db.Float, nullable=True)

    # Context
    context_type = db.Column(db.String(50), nullable=True)  # 'research', 'transaction', 'portfolio'
    context_id = db.Column(db.Integer, nullable=True)

    # Validation (filled in later when outcome is known)
    actual_value = db.Column(db.Float, nullable=True)
    actual_label = db.Column(db.String(100), nullable=True)
    prediction_error = db.Column(db.Float, nullable=True)  # For regression: actual - predicted
    was_correct = db.Column(db.Boolean, nullable=True, index=True)  # For classification
    validated_at = db.Column(db.DateTime, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=now_utc)

    # Relationships
    user = db.relationship('User', backref=db.backref('ml_predictions', lazy='dynamic'))

    def __repr__(self):
        return f'<MLPredictionLog {self.id}: {self.model_name} v{self.model_version}>'
