# app/models/idea_pipeline.py

from app import db
from app.utils.time_utils import now_utc


class IdeaPipeline(db.Model):
    __tablename__ = 'idea_pipeline'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    idea_type = db.Column(db.String(50), nullable=False, default='company')  # Subject type: company/sector/theme
    idea_purpose = db.Column(db.String(50), nullable=False, default='investment')  # Purpose: investment/learning/research
    ticker_symbol = db.Column(db.String(20))
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'))  # Associated company for company-type ideas
    sector_id = db.Column(db.Integer, db.ForeignKey('sector.id'), nullable=True, index=True)  # Sector for analytics
    source = db.Column(db.String(200))
    thesis_summary = db.Column(db.Text)
    initial_notes = db.Column(db.Text)
    status = db.Column(db.String(50), default='inbox', index=True)
    kill_reason = db.Column(db.Text)
    failed_criterion_id = db.Column(db.Integer, db.ForeignKey('kill_criterion.id'))

    # Circle of Competence tracking (for Too Hard Basket analytics)
    within_circle_of_competence = db.Column(db.String(20))  # 'yes', 'no', 'unsure'

    created_at = db.Column(db.DateTime, default=now_utc)
    killed_at = db.Column(db.DateTime)
    promoted_at = db.Column(db.DateTime)
    last_reviewed_at = db.Column(db.DateTime)
    priority = db.Column(db.Integer, default=0)
    promoted_to_company_id = db.Column(db.Integer, db.ForeignKey('company.id'))
    kill_sessions = db.relationship('KillSession', backref='idea', lazy='dynamic', cascade='all, delete-orphan')
    company = db.relationship('Company', foreign_keys=[company_id])
    sector = db.relationship('Sector', backref='ideas')
    promoted_to_company = db.relationship('Company', foreign_keys=[promoted_to_company_id])

    def __repr__(self):
        return f'<IdeaPipeline {self.name} - {self.status}>'


class KillChecklist(db.Model):
    __tablename__ = 'kill_checklist'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    is_default = db.Column(db.Boolean, default=False)
    applicable_to = db.Column(db.String(100), default='all')
    criteria = db.relationship('KillCriterion', backref='kill_checklist', lazy='dynamic', cascade='all, delete-orphan', order_by='KillCriterion.order')
    kill_sessions = db.relationship('KillSession', backref='checklist', lazy='dynamic', cascade='all, delete-orphan')
    total_ideas_evaluated = db.Column(db.Integer, default=0)
    total_ideas_killed = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=now_utc)
    updated_at = db.Column(db.DateTime, default=now_utc, onupdate=now_utc)

    @property
    def kill_rate(self):
        if self.total_ideas_evaluated == 0: return 0
        return round((self.total_ideas_killed / self.total_ideas_evaluated) * 100, 1)

    @property
    def criteria_count(self):
        return self.criteria.count()

    def __repr__(self):
        return f'<KillChecklist {self.name}>'


class KillCriterion(db.Model):
    __tablename__ = 'kill_criterion'
    id = db.Column(db.Integer, primary_key=True)
    kill_checklist_id = db.Column(db.Integer, db.ForeignKey('kill_checklist.id'), nullable=False)
    question = db.Column(db.String(500), nullable=False)
    failure_reason = db.Column(db.Text)
    help_text = db.Column(db.Text)
    order = db.Column(db.Integer, default=0)
    times_evaluated = db.Column(db.Integer, default=0)
    times_failed = db.Column(db.Integer, default=0)

    # New fields for Dynamic Kill Checklist
    effectiveness_score = db.Column(db.Float, default=0.0)
    last_calculated = db.Column(db.DateTime)
    auto_suggested = db.Column(db.Boolean, default=False)
    source_mistake_id = db.Column(db.Integer, db.ForeignKey('mistake_log.id'))
    created_at = db.Column(db.DateTime, default=now_utc)
    last_used = db.Column(db.DateTime)

    killed_ideas = db.relationship('IdeaPipeline', backref='failed_criterion', foreign_keys='IdeaPipeline.failed_criterion_id')
    source_mistake = db.relationship('MistakeLog', backref='generated_criteria')

    @property
    def failure_rate(self):
        if self.times_evaluated == 0: return 0
        return round((self.times_failed / self.times_evaluated) * 100, 1)

    def __repr__(self):
        return f'<KillCriterion {self.question[:50]}>'


class KillSession(db.Model):
    __tablename__ = 'kill_session'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    idea_id = db.Column(db.Integer, db.ForeignKey('idea_pipeline.id'), nullable=False)
    kill_checklist_id = db.Column(db.Integer, db.ForeignKey('kill_checklist.id'), nullable=False)
    started_at = db.Column(db.DateTime, default=now_utc)
    completed_at = db.Column(db.DateTime)
    outcome = db.Column(db.String(50))  # 'killed', 'survived', 'paused'
    answers = db.relationship('KillAnswer', backref='session', lazy='dynamic', cascade='all, delete-orphan')
    time_taken_seconds = db.Column(db.Integer)

    def __repr__(self):
        return f'<KillSession for Idea {self.idea_id}>'


class KillAnswer(db.Model):
    __tablename__ = 'kill_answer'
    id = db.Column(db.Integer, primary_key=True)
    kill_session_id = db.Column(db.Integer, db.ForeignKey('kill_session.id'), nullable=False)
    criterion_id = db.Column(db.Integer, db.ForeignKey('kill_criterion.id'), nullable=False)
    passed = db.Column(db.Boolean)
    notes = db.Column(db.Text)
    answered_at = db.Column(db.DateTime, default=now_utc)
    criterion = db.relationship('KillCriterion')

    def __repr__(self):
        return f'<KillAnswer {self.passed}>'


class KillChecklistSuggestion(db.Model):
    """
    Intelligent suggestions for optimizing Kill Checklists based on usage patterns and mistakes.
    This model tracks all suggestions made by the system and user responses to them.
    """
    __tablename__ = 'kill_checklist_suggestion'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    kill_checklist_id = db.Column(db.Integer, db.ForeignKey('kill_checklist.id'), nullable=False)

    # Suggestion details
    suggestion_type = db.Column(db.String(50), nullable=False)
    # Types: 'reorder_criteria', 'add_criterion', 'remove_criterion', 'modify_criterion', 'merge_criteria'

    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    reasoning = db.Column(db.Text)  # Why this suggestion was made

    # Suggestion data (JSON format for flexibility)
    suggestion_data = db.Column(db.JSON, nullable=False)
    # Example for reorder: {"from_positions": [1,2,3], "to_positions": [3,1,2], "criteria_ids": [10,11,12]}
    # Example for add: {"question": "Is debt-to-equity < 0.3?", "position": 2, "source": "mistake_log"}

    # Performance prediction
    effectiveness_gain = db.Column(db.Float)  # Predicted improvement percentage
    confidence_score = db.Column(db.Float, default=0.5)  # 0-1 confidence in suggestion

    # Tracking
    created_at = db.Column(db.DateTime, default=now_utc)
    status = db.Column(db.String(20), default='pending')  # 'pending', 'accepted', 'rejected', 'auto_applied'
    responded_at = db.Column(db.DateTime)

    # Source information
    trigger_event = db.Column(db.String(100))  # 'evaluation_milestone', 'mistake_logged', 'periodic_analysis'
    source_data = db.Column(db.JSON)  # Related mistake_id, evaluation_count, etc.

    # Relationships
    checklist = db.relationship('KillChecklist', backref='suggestions')
    user = db.relationship('User')

    @property
    def age_hours(self):
        """How many hours old is this suggestion"""
        if not self.created_at:
            return 0
        return (now_utc() - self.created_at).total_seconds() / 3600

    @property
    def is_expired(self):
        """Suggestions expire after 30 days if not acted upon"""
        return self.age_hours > (30 * 24)

    def __repr__(self):
        return f'<KillChecklistSuggestion {self.suggestion_type}: {self.title[:30]}>'


class IdeaSourceAnalysis(db.Model):
    """
    Track the quality of different idea sources to identify
    which inputs generate the best investment opportunities.
    """
    __tablename__ = 'idea_source_analysis'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    source_name = db.Column(db.String(200), nullable=False)

    # Volume metrics
    total_ideas = db.Column(db.Integer, default=0)
    ideas_killed = db.Column(db.Integer, default=0)
    ideas_promoted = db.Column(db.Integer, default=0)
    ideas_invested = db.Column(db.Integer, default=0)

    # Quality metrics
    survival_rate = db.Column(db.Float)  # % that pass kill test
    investment_rate = db.Column(db.Float)  # % that become investments
    average_research_hours = db.Column(db.Float)
    average_confidence = db.Column(db.Float)

    # Outcome tracking
    successful_investments = db.Column(db.Integer, default=0)
    failed_investments = db.Column(db.Integer, default=0)
    average_return = db.Column(db.Float)

    last_idea_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=now_utc)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'source_name', name='_user_source_uc'),
    )

    def __repr__(self):
        return f'<IdeaSourceAnalysis {self.source_name}>'


class MistakeLog(db.Model):
    """
    Detailed log of investment mistakes for pattern recognition and learning.
    """
    __tablename__ = 'mistake_log'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Mistake details
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)

    # Categorization
    mistake_type = db.Column(db.String(100), nullable=False)
    # Types: 'analysis_error', 'emotional_decision', 'process_failure',
    # 'information_gap', 'timing', 'position_sizing', 'thesis_drift'

    severity = db.Column(db.Integer, default=5)  # 1-10 scale
    cost_estimate = db.Column(db.Float)  # Estimated $ cost or % loss

    # Context
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'))
    decision_id = db.Column(db.Integer, db.ForeignKey('decision_journal.id'))
    occurred_date = db.Column(db.Date)

    # Root cause analysis
    root_cause = db.Column(db.Text)
    contributing_factors = db.Column(db.JSON)  # List of factors

    # Prevention
    lesson_learned = db.Column(db.Text, nullable=False)
    prevention_steps = db.Column(db.JSON)  # List of steps to prevent recurrence
    process_changes = db.Column(db.Text)  # Changes made to investment process

    # Review tracking
    times_reviewed = db.Column(db.Integer, default=0)
    last_reviewed = db.Column(db.DateTime)
    prevented_similar = db.Column(db.Integer, default=0)  # Times prevented similar mistake

    created_at = db.Column(db.DateTime, default=now_utc)
    updated_at = db.Column(db.DateTime, default=now_utc, onupdate=now_utc)

    # Relationships
    company = db.relationship('Company', backref='mistake_logs')
    decision = db.relationship('DecisionJournal', backref='mistakes')

    def __repr__(self):
        return f'<MistakeLog {self.title}>'
