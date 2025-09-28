# company_research_platform/app/models.py

from app import db  # Import the db instance from app/__init__.py
from datetime import datetime, timezone
from app.utils.time_utils import now_utc, ensure_timezone_aware
from werkzeug.security import (
    generate_password_hash,
    check_password_hash,
)  # Import hashing functions
from flask_login import UserMixin  # Import UserMixin
from app import login_manager  # Import login_manager from app/__init__.py

favorite_companies = db.Table(
    "favorite_companies",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("company_id", db.Integer, db.ForeignKey("company.id"), primary_key=True),
)

competitors_association = db.Table(
    "competitors_association",
    db.Column("company_id", db.Integer, db.ForeignKey("company.id"), primary_key=True),
    db.Column(
        "competitor_id", db.Integer, db.ForeignKey("company.id"), primary_key=True
    ),
)


# User loader function required by Flask-Login
# This function is called to reload the user object from the user ID stored in the session
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# The User class needs to inherit from UserMixin
class User(UserMixin, db.Model):  # Add UserMixin here
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    email = db.Column(db.String(120), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    uploaded_documents = db.relationship(
        "CompanyDocument", backref="uploader", lazy="dynamic"
    )
    checklists = db.relationship("Checklist", backref="author", lazy="dynamic")
    research_sessions = db.relationship(
        "ResearchSession", backref="researcher", lazy="dynamic"
    )
    companies = db.relationship("Company", backref="creator", lazy="dynamic")
    favorites = db.relationship(
        "Company",
        secondary=favorite_companies,
        lazy="dynamic",
        backref=db.backref("favorited_by", lazy="dynamic"),
    )
    destination_checkpoints = db.relationship(
        "DestinationCheckpoint", backref="creator", lazy="dynamic"
    )
    subscription_tier  = db.Column(db.String(50), nullable=False, default="free")
    question_bank_items = db.relationship(
        "QuestionBankItem",
        backref="author",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    sector_analyses = db.relationship(
        "SectorAnalysis", backref="author", lazy="dynamic", cascade="all, delete-orphan"
    )
    idea_pipeline = db.relationship('IdeaPipeline', backref='author', 
                                   lazy='dynamic', cascade='all, delete-orphan')
    kill_checklists = db.relationship('KillChecklist', backref='author', 
                                     lazy='dynamic', cascade='all, delete-orphan')
    kill_sessions = db.relationship('KillSession', backref='user', 
                                   lazy='dynamic', cascade='all, delete-orphan')
    research_templates = db.relationship('ResearchTemplate', backref='author', 
                                        lazy='dynamic', cascade='all, delete-orphan')
    research_projects = db.relationship('ResearchProject', backref='researcher', 
                                       lazy='dynamic', cascade='all, delete-orphan')
    work_sessions = db.relationship('WorkSession', backref='user', 
                                   lazy='dynamic', cascade='all, delete-orphan')
    template_steps = db.relationship('TemplateStep', backref='creator', 
                                    lazy='dynamic', cascade='all, delete-orphan')
    metrics = db.relationship('ResearchMetrics', backref='user', 
                             uselist=False, cascade='all, delete-orphan')
    source_analyses = db.relationship('IdeaSourceAnalysis', backref='user',
                                     lazy='dynamic', cascade='all, delete-orphan')
    research_logs = db.relationship('ResearchLog', backref='user',
                                   lazy='dynamic', cascade='all, delete-orphan')
    decision_journals = db.relationship('DecisionJournal', backref='user',
                                       lazy='dynamic', cascade='all, delete-orphan')
    journal_entries = db.relationship('JournalEntry', backref='author',
                                     lazy='dynamic', cascade='all, delete-orphan')
    thesis_evolutions = db.relationship('ThesisEvolution', backref='author',
                                       lazy='dynamic', cascade='all, delete-orphan')
    learning_notes = db.relationship('LearningNote', backref='author',
                                    lazy='dynamic', cascade='all, delete-orphan')
    journal_templates = db.relationship('JournalTemplate', backref='author',
                                       lazy='dynamic', cascade='all, delete-orphan')
    mistake_logs = db.relationship('MistakeLog', backref='user',
                                  lazy='dynamic', cascade='all, delete-orphan')
    weekly_reviews = db.relationship('WeeklyReview', backref='user',
                                    lazy='dynamic', cascade='all, delete-orphan')
    postmortems = db.relationship('InvestmentPostMortem', backref='user',
                                 lazy='dynamic', cascade='all, delete-orphan')
    learning_paths = db.relationship('LearningPath', backref='user',
                                    lazy='dynamic', cascade='all, delete-orphan')
    patterns = db.relationship('PatternRecognition', backref='user',
                              lazy='dynamic', cascade='all, delete-orphan')

    # Onboarding tracking
    onboarding_completed = db.Column(db.Boolean, default=False)
    onboarding_step = db.Column(db.Integer, default=0)  # Track current step (0-5)
    onboarding_started_at = db.Column(db.DateTime)
    onboarding_completed_at = db.Column(db.DateTime)

    # User preferences
    preferred_sprint_duration = db.Column(db.Integer, default=30)  # minutes
    research_experience_level = db.Column(db.String(20), default='intermediate')  # beginner, intermediate, expert
    notification_preferences = db.Column(db.JSON, default={'pattern_alerts': True, 'weekly_review': True, 'fomo_alerts': True})

    # Community features
    buddy_system_enabled = db.Column(db.Boolean, default=False)
    peer_feedback_count = db.Column(db.Integer, default=0)
    community_reputation = db.Column(db.Integer, default=0)

    # FOMO protection
    last_fomo_alert = db.Column(db.DateTime)
    fomo_protection_level = db.Column(db.String(20), default='medium')  # low, medium, high

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        # Ensure password_hash is not None before checking
        if self.password_hash is None:
            return False
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username}>"


class Checklist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(1000))
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False
    )  # Link to User

    # Relationships: A checklist has many items
    items = db.relationship(
        "ChecklistItem",
        backref="checklist",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Checklist {self.name}>"


class ChecklistItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500), nullable=False)
    checklist_id = db.Column(
        db.Integer, db.ForeignKey("checklist.id"), nullable=False
    )  # Link to Checklist
    parent_id = db.Column(
        db.Integer, db.ForeignKey("checklist_item.id"), nullable=True
    )  # For sub-items
    order = db.Column(db.Integer, default=0)  # To maintain order

    # If this field is populated, it indicates the item can leverage LLM analysis
    # and this text can be used as the basis for the LLM query
    llm_prompt = db.Column(db.Text, nullable=True, default=None)

    # Relationship: A checklist item can have sub-items (children)
    children = db.relationship(
        "ChecklistItem",
        backref=db.backref("parent", remote_side=[id]),
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<ChecklistItem {self.text[:30]}...>"


class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    ticker_symbol = db.Column(db.String(20), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    summary = db.Column(db.Text, nullable=True)
    sector = db.Column(db.String(100), nullable=True)
    industry = db.Column(db.String(150), nullable=True)
    intrinsic_value = db.Column(db.BigInteger, nullable=True)
    is_in_portfolio = db.Column(db.Boolean, default=False, nullable=False, index=True)

    # Relationships
    research_sessions = db.relationship(
        "ResearchSession",
        backref="company",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    documents = db.relationship(
        "CompanyDocument",
        backref="company",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    articles = db.relationship(
        "CompanyArticle",
        backref="company",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    destination_checkpoints = db.relationship(
        "DestinationCheckpoint",
        backref="company",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    scuttlebutt_analyses = db.relationship(
        "ScuttlebuttAnalysis",
        backref="company",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    qualitative_analyses = db.relationship(
        "QualitativeAnalysis",
        backref="company",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    financial_data = db.relationship(
        "FinancialData", backref="company", lazy="dynamic", cascade="all, delete-orphan"
    )

    competitors = db.relationship(
        "Company",  # The relationship is with the Company model itself
        secondary=competitors_association,  # Use our association table to link them
        primaryjoin=(competitors_association.c.company_id == id),
        secondaryjoin=(competitors_association.c.competitor_id == id),
        backref=db.backref(
            "competed_by", lazy="dynamic"
        ),  # Allows finding who competes WITH this company
        lazy="dynamic",
    )

    def __repr__(self):
        return f"<Company {self.ticker_symbol} - {self.name}>"


class ResearchSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    start_date = db.Column(db.DateTime, nullable=False, default=now_utc)
    status = db.Column(db.String(50), nullable=False, default="in_progress")

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False)
    checklist_id = db.Column(db.Integer, db.ForeignKey("checklist.id"), nullable=False)
    conclusion = db.Column(db.Text, nullable=True)

    # Relationships:
    # The 'company' attribute is created by the backref from the Company model.
    # If your User model has a 'research_sessions' relationship with a backref='researcher',
    # then session.researcher would be available.

    # ADD/ENSURE THIS RELATIONSHIP FOR CHECKLIST:
    checklist = db.relationship("Checklist")

    # You might also want a direct relationship to the User if not using a backref that names it 'user'
    # user = db.relationship('User') # If User model's backref isn't simply 'user'

    answers = db.relationship(
        "ResearchAnswer",
        backref="session",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<ResearchSession {self.id} for Company {self.company_id} using Checklist {self.checklist_id}>"


class ResearchAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    answer_text = db.Column(db.Text, nullable=True)  # Textual answer from the user
    # file_path: For later, when we implement PDF uploads for specific questions
    # file_path = db.Column(db.String(300), nullable=True)
    answered_at = db.Column(db.DateTime, default=now_utc)
    satisfaction_status = db.Column(db.String(30), nullable=True, default="neutral")

    research_session_id = db.Column(
        db.Integer, db.ForeignKey("research_session.id"), nullable=False
    )
    checklist_item_id = db.Column(
        db.Integer, db.ForeignKey("checklist_item.id"), nullable=False
    )

    # Relationship to the specific checklist item this answer pertains to
    item = db.relationship("ChecklistItem")

    def __repr__(self):
        return f"<ResearchAnswer {self.id} for Item {self.checklist_item_id} in Session {self.research_session_id}>"


class CompanyDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # Foreign key to link this document to a Company
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False)

    # Foreign key to link this document to the User who uploaded it
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    original_filename = db.Column(
        db.String(255), nullable=False
    )  # Original name of the uploaded file
    # Stored file path, relative to a base upload directory.
    # Could be a unique generated filename or include subdirectories like company_id/
    stored_filename = db.Column(db.String(300), nullable=False, unique=True)

    document_group = db.Column(
        db.String(100), nullable=False, index=True
    )  # E.g., 'Annual Reports', 'Quarterly Reports', 'Analyst Transcripts'
    document_title = db.Column(
        db.String(255), nullable=True
    )  # E.g., "2023 Annual Report", "Q4 2023 Earnings Call"
    document_date = db.Column(
        db.Date, nullable=True
    )  # Publication date of the document, or period end date

    description = db.Column(db.Text, nullable=True)  # Optional user description
    uploaded_at = db.Column(db.DateTime, nullable=False, default=now_utc)

    # Relationships (these will create the backrefs on Company and User)
    # company = db.relationship('Company', backref=db.backref('documents', lazy='dynamic')) # This is one way
    # uploader = db.relationship('User', backref=db.backref('uploaded_documents', lazy='dynamic')) # This is one way

    def __repr__(self):
        return (
            f"<CompanyDocument {self.original_filename} for Company {self.company_id}>"
        )


class DestinationCheckpoint(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # Foreign key to link this checkpoint to a specific Company
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False)

    # Foreign key to link this checkpoint to the User who created it
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    target_date = db.Column(db.Date, nullable=False, index=True)
    metric = db.Column(
        db.String(200), nullable=False
    )  # E.g., "Quarterly Revenue", "EPS", "Product Launch"
    expectation = db.Column(
        db.Text, nullable=False
    )  # E.g., ">$5 Billion", "Successful and on time"

    # This will be updated by the user later
    status = db.Column(
        db.String(30), nullable=False, default="Active"
    )  # E.g., 'Active', 'Met', 'Not Met'
    outcome_notes = db.Column(db.Text, nullable=True)  # User's analysis of the outcome

    created_at = db.Column(db.DateTime, nullable=False, default=now_utc)

    def __repr__(self):
        return f"<DestinationCheckpoint {self.metric} for Company {self.company_id}>"


class CompanyArticle(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # Foreign key to link this article to a Company
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False)

    # The title of the article
    title = db.Column(db.String(300), nullable=False)

    # The URL to the original article - should be unique to avoid duplicates
    url = db.Column(db.String(500), nullable=False, unique=True)

    # A short description or snippet of the article
    description = db.Column(db.Text, nullable=True)

    # The name of the news source (e.g., "Reuters", "Bloomberg")
    source_name = db.Column(db.String(100), nullable=True)

    # The original publication date of the article
    published_at = db.Column(db.DateTime, nullable=False, index=True)

    # The date we fetched the article
    fetched_at = db.Column(db.DateTime, nullable=False, default=now_utc)

    def __repr__(self):
        return f"<CompanyArticle {self.title[:50]}...>"


class ScuttlebuttAnalysis(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # Foreign key to link this analysis to a Company
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False)

    # The full summary text generated by the AI
    generated_summary = db.Column(db.Text, nullable=False)

    # The date the analysis was generated
    generated_at = db.Column(
        db.DateTime, nullable=False, default=now_utc, index=True
    )

    def __repr__(self):
        return f"<ScuttlebuttAnalysis for Company {self.company_id} on {self.generated_at}>"


class QualitativeAnalysis(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # Foreign key to link this analysis to a Company
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False)

    # Foreign key to link this analysis to the User who created it
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    # This field will store which model is being used, e.g., 'SWOT'
    model_type = db.Column(db.String(50), nullable=False, index=True)

    # We'll use a JSON field to store the structured data.
    # For SWOT, it will look like: {"strengths": "...", "weaknesses": "...", ...}
    content = db.Column(db.JSON, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=now_utc)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=now_utc, onupdate=now_utc
    )

    # Ensure a user can only have one of each analysis type per company
    __table_args__ = (
        db.UniqueConstraint(
            "company_id", "user_id", "model_type", name="uq_user_company_analysis"
        ),
    )

    def __repr__(self):
        return f"<QualitativeAnalysis {self.model_type} for Company {self.company_id}>"

class FinancialData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False)

    # e.g., 'income_statement', 'balance_sheet', 'cash_flow'
    statement_type = db.Column(db.String(50), nullable=False, index=True)

    # The name of the line item, e.g., 'Total Revenue', 'Net Income'
    metric_name = db.Column(db.String(100), nullable=False, index=True)

    # The end date of the financial period (e.g., year or quarter end)
    period_date = db.Column(db.Date, nullable=False, index=True)

    # The actual value of the metric
    value = db.Column(db.BigInteger, nullable=False)

    # Ensure we only have one value for each metric on a specific date for a company
    __table_args__ = (
        db.UniqueConstraint(
            "company_id", "metric_name", "period_date", name="uq_company_metric_period"
        ),
    )

    def __repr__(self):
        return f"<FinancialData {self.metric_name} for Company {self.company_id} on {self.period_date}>"

class QuestionBankItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    # The text of the reusable question
    text = db.Column(db.Text, nullable=False)

    # An optional, reusable LLM prompt for this question
    llm_prompt = db.Column(db.Text, nullable=True)

    # The sector tag to categorize the question. Can be null for general questions.
    sector = db.Column(db.String(100), nullable=True, index=True)

    created_at = db.Column(db.DateTime, nullable=False, default=now_utc)

    def __repr__(self):
        return f"<QuestionBankItem {self.text[:50]}...>"

class SectorAnalysis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    # The name of the sector being analyzed
    sector_name = db.Column(db.String(100), nullable=False, index=True)

    # A large text field for free-form research notes
    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=now_utc)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=now_utc, onupdate=now_utc
    )

    # Ensure a user can only have one analysis notebook per sector name
    __table_args__ = (
        db.UniqueConstraint("user_id", "sector_name", name="uq_user_sector"),
    )

    def __repr__(self):
        return f'<SectorAnalysis for "{self.sector_name}" by User {self.user_id}>'

class IdeaPipeline(db.Model):
    __tablename__ = 'idea_pipeline'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    idea_type = db.Column(db.String(50), nullable=False, default='company')  # Subject type: company/sector/theme
    idea_purpose = db.Column(db.String(50), nullable=False, default='investment')  # Purpose: investment/learning/research
    ticker_symbol = db.Column(db.String(20))
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'))  # Associated company for company-type ideas
    source = db.Column(db.String(200))
    thesis_summary = db.Column(db.Text)
    initial_notes = db.Column(db.Text)
    status = db.Column(db.String(50), default='inbox', index=True)
    kill_reason = db.Column(db.Text)
    failed_criterion_id = db.Column(db.Integer, db.ForeignKey('kill_criterion.id'))
    created_at = db.Column(db.DateTime, default=now_utc)
    killed_at = db.Column(db.DateTime)
    promoted_at = db.Column(db.DateTime)
    last_reviewed_at = db.Column(db.DateTime)
    priority = db.Column(db.Integer, default=0)
    promoted_to_company_id = db.Column(db.Integer, db.ForeignKey('company.id'))
    kill_sessions = db.relationship('KillSession', backref='idea', lazy='dynamic', cascade='all, delete-orphan')
    company = db.relationship('Company', foreign_keys=[company_id])
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
    criteria = db.relationship('KillCriterion', backref='kill_checklist', lazy='dynamic', cascade='all, delete-orphan', order_by='KillCriterion.order')

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
# Add these new models to app/models.py after your existing IdeaPipeline models

class ResearchTemplate(db.Model):
    """
    A research template is a reusable workflow that defines how an investor
    analyzes opportunities. Think of it as a 'recipe' for research that ensures
    consistency while allowing flexibility for different investment styles.
    """
    __tablename__ = 'research_template'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Basic template information
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    investment_style = db.Column(db.String(100))  # 'value', 'growth', 'special_situations', etc.
    research_subject_types = db.Column(db.JSON)  # ['company', 'sector', 'theme', 'market', 'strategy']
    
    # The workflow is stored as JSON to allow maximum flexibility
    # Each step can reference different types of analysis tools
    workflow_steps = db.Column(db.JSON, nullable=False)
    
    # Templates can be shared with the community (future feature)
    is_public = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    
    # Track usage and effectiveness
    times_used = db.Column(db.Integer, default=0)
    successful_investments = db.Column(db.Integer, default=0)
    failed_investments = db.Column(db.Integer, default=0)
    average_research_hours = db.Column(db.Float)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=now_utc)
    updated_at = db.Column(db.DateTime, default=now_utc, onupdate=now_utc)
    
    # Relationships
    research_projects = db.relationship('ResearchProject', backref='template', 
                                       lazy='dynamic', cascade='all, delete-orphan')
    
    @property
    def success_rate(self):
        """Calculate the success rate of investments made using this template"""
        total = self.successful_investments + self.failed_investments
        if total == 0:
            return 0
        return round((self.successful_investments / total) * 100, 1)
    
    @property
    def step_count(self):
        """Number of steps in this template's workflow"""
        return len(self.workflow_steps) if self.workflow_steps else 0
    
    def get_step(self, step_index):
        """Safely get a specific step from the workflow"""
        if self.workflow_steps and 0 <= step_index < len(self.workflow_steps):
            return self.workflow_steps[step_index]
        return None
    
    def __repr__(self):
        return f'<ResearchTemplate {self.name}>'


class ResearchProject(db.Model):
    """
    A research project is an active execution of a research template for any research subject
    (companies, sectors, markets, themes, strategies). It tracks progress, time spent, 
    findings, and ultimately research conclusions or investment decisions.
    """
    __tablename__ = 'research_project'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey('research_template.id'), nullable=False)
    
    # Multi-subject research support
    research_subject_type = db.Column(db.String(50), nullable=False, default='company')  # 'company', 'sector', 'market', 'strategy', 'theme'
    research_subject_name = db.Column(db.String(200))  # Human-readable subject name
    
    # Subject-specific foreign keys (nullable for flexibility)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'))  # For company research
    # sector_id will be added when Sector model is created
    # market_id, theme_id, etc. can be added later as needed
    
    # If this project originated from an idea in the pipeline
    idea_id = db.Column(db.Integer, db.ForeignKey('idea_pipeline.id'))
    
    # Project metadata
    project_name = db.Column(db.String(200))
    investment_thesis = db.Column(db.Text)  # Evolving thesis as research progresses
    
    # Progress tracking
    current_step_index = db.Column(db.Integer, default=0)
    completed_steps = db.Column(db.JSON, default=list)  # Array of completed step indices
    step_notes = db.Column(db.JSON, default=dict)  # Notes for each step
    step_results = db.Column(db.JSON, default=dict)  # Detailed results for each step
    
    # Status tracking
    status = db.Column(db.String(50), default='active')  # 'active', 'paused', 'completed', 'abandoned', 'killed'
    kill_reason = db.Column(db.Text)  # Reason for killing the investment during screening
    
    # Time tracking - crucial for understanding where effort goes
    total_hours_spent = db.Column(db.Float, default=0.0)
    time_per_step = db.Column(db.JSON, default=dict)  # Track time for each step
    last_worked_at = db.Column(db.DateTime)
    
    # Decision tracking
    decision = db.Column(db.String(50))  # 'invest', 'pass', 'watchlist', 'needs_more_work'
    decision_date = db.Column(db.DateTime)
    decision_confidence = db.Column(db.Integer)  # 1-10 scale
    decision_notes = db.Column(db.Text)
    
    # If invested, track the outcome
    investment_amount = db.Column(db.Float)
    investment_date = db.Column(db.Date)
    exit_date = db.Column(db.Date)
    return_percentage = db.Column(db.Float)
    
    # Key findings that influenced the decision
    key_findings = db.Column(db.JSON, default=list)
    red_flags = db.Column(db.JSON, default=list)
    green_flags = db.Column(db.JSON, default=list)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=now_utc)
    completed_at = db.Column(db.DateTime)
    
    # Relationships
    company = db.relationship('Company', backref='research_projects')
    idea = db.relationship('IdeaPipeline', backref='research_project')
    work_sessions = db.relationship('WorkSession', backref='project',
                                   lazy='dynamic', cascade='all, delete-orphan')
    research_logs = db.relationship('ResearchLog', backref='project',
                                   lazy='dynamic', cascade='all, delete-orphan')
    
    @property
    def progress_percentage(self):
        """Calculate the completion percentage of this project"""
        if not self.template or not self.template.workflow_steps:
            return 0
        total_steps = len(self.template.workflow_steps)
        if total_steps == 0:
            return 0
        return round((len(self.completed_steps) / total_steps) * 100, 1)
    
    @property
    def current_step(self):
        """Get the current step details from the template"""
        if self.template:
            return self.template.get_step(self.current_step_index)
        return None
    
    @property
    def is_overdue(self):
        """Check if this project has been idle too long"""
        if self.status != 'active' or not self.last_worked_at:
            return False
        last_worked_at_aware = ensure_timezone_aware(self.last_worked_at)
        current_time = now_utc()
        days_idle = (current_time - last_worked_at_aware).days
        return days_idle > 14  # Consider overdue after 2 weeks of inactivity
    
    @property
    def research_subject(self):
        """Get the actual research subject object"""
        if self.research_subject_type == 'company' and self.company:
            return self.company
        # Sectors, markets, themes, strategies use research_subject_name for now
        # TODO: Add dedicated models and relationships as needed
        return None
    
    @property 
    def subject_display_name(self):
        """Get display name for the research subject"""
        if self.research_subject_name:
            return self.research_subject_name
        elif self.research_subject:
            return getattr(self.research_subject, 'name', str(self.research_subject))
        return f"Unknown {self.research_subject_type}"
    
    @property
    def subject_type_display(self):
        """Get human-readable research subject type"""
        type_map = {
            'company': 'Company',
            'sector': 'Sector', 
            'market': 'Market',
            'theme': 'Theme',
            'strategy': 'Strategy'
        }
        return type_map.get(self.research_subject_type, self.research_subject_type.title())
    
    @property
    def requires_kill_checklist(self):
        """Determine if this research subject type typically needs kill checklist screening"""
        # Companies always need screening due to high volume
        if self.research_subject_type == 'company':
            return True
        # Sectors might need screening (template-configurable) 
        elif self.research_subject_type == 'sector':
            return False  # Template will decide
        # Markets, themes, strategies typically skip screening
        else:
            return False
    
    def __repr__(self):
        return f'<ResearchProject {self.project_name or f"{self.subject_type_display}: {self.subject_display_name}"}>'


class WorkSession(db.Model):
    """
    A work session tracks individual research sessions within a project.
    This granular tracking helps investors understand their time allocation
    and identify which parts of their process are most time-consuming.
    """
    __tablename__ = 'work_session'
    
    id = db.Column(db.Integer, primary_key=True)
    research_project_id = db.Column(db.Integer, db.ForeignKey('research_project.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # What was worked on
    step_index = db.Column(db.Integer)
    step_name = db.Column(db.String(200))
    
    # Time tracking
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime)
    duration_minutes = db.Column(db.Integer)
    
    # Work product
    notes = db.Column(db.Text)
    findings = db.Column(db.JSON)  # Structured findings
    documents_reviewed = db.Column(db.JSON)  # List of documents consulted
    
    # Quality markers
    confidence_level = db.Column(db.Integer)  # 1-10 scale for this session's work
    needs_followup = db.Column(db.Boolean, default=False)
    followup_notes = db.Column(db.Text)
    
    def __repr__(self):
        return f'<WorkSession {self.id} for Project {self.research_project_id}>'


class TemplateStep(db.Model):
    """
    A library of reusable research steps that can be assembled into templates.
    This allows users to build templates from pre-defined components while
    still maintaining flexibility to create custom steps.
    """
    __tablename__ = 'template_step'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Null for system-provided steps
    
    # Step definition
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    step_type = db.Column(db.String(50), nullable=False)  # 'checklist', 'model', 'document_review', 'valuation', 'custom'
    
    # Configuration for the step
    config = db.Column(db.JSON)  # Type-specific configuration
    
    # Expected time and importance
    estimated_minutes = db.Column(db.Integer, default=60)
    is_critical = db.Column(db.Boolean, default=False)  # Must be completed
    
    # Guidance for completing this step
    instructions = db.Column(db.Text)
    success_criteria = db.Column(db.Text)
    common_pitfalls = db.Column(db.Text)
    
    # For learning and improvement
    times_used = db.Column(db.Integer, default=0)
    average_actual_minutes = db.Column(db.Float)
    skip_rate = db.Column(db.Float)  # How often this step gets skipped
    
    # Categorization
    category = db.Column(db.String(100))  # 'fundamental', 'technical', 'qualitative', etc.
    tags = db.Column(db.JSON, default=list)
    
    created_at = db.Column(db.DateTime, default=now_utc)
    
    def __repr__(self):
        return f'<TemplateStep {self.name}>'    
    
# Add these new models to app/models.py

class ResearchMetrics(db.Model):
    """
    Aggregated metrics for a user's research performance.
    Updated periodically to provide dashboard insights.
    """
    __tablename__ = 'research_metrics'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    
    # Idea Pipeline Metrics
    total_ideas_captured = db.Column(db.Integer, default=0)
    ideas_killed = db.Column(db.Integer, default=0)
    ideas_promoted = db.Column(db.Integer, default=0)
    ideas_in_pipeline = db.Column(db.Integer, default=0)
    average_days_to_decision = db.Column(db.Float)
    
    # Kill Rate Analysis
    kill_rate = db.Column(db.Float)  # Percentage
    most_common_kill_reason = db.Column(db.String(500))
    fastest_kill_minutes = db.Column(db.Integer)
    slowest_kill_minutes = db.Column(db.Integer)
    
    # Research Time Metrics
    total_research_hours = db.Column(db.Float, default=0)
    average_hours_per_company = db.Column(db.Float)
    average_hours_per_decision = db.Column(db.Float)
    most_time_consuming_step = db.Column(db.String(200))
    
    # Decision Quality Metrics
    total_investment_decisions = db.Column(db.Integer, default=0)
    invest_decisions = db.Column(db.Integer, default=0)
    pass_decisions = db.Column(db.Integer, default=0)
    average_confidence_score = db.Column(db.Float)
    
    # Success Tracking (if they track outcomes)
    winning_investments = db.Column(db.Integer, default=0)
    losing_investments = db.Column(db.Integer, default=0)
    average_return = db.Column(db.Float)
    best_investment_return = db.Column(db.Float)
    worst_investment_return = db.Column(db.Float)
    
    # Source Quality
    best_idea_source = db.Column(db.String(200))
    best_source_success_rate = db.Column(db.Float)
    
    # Behavioral Patterns
    most_productive_day = db.Column(db.String(20))  # Monday, Tuesday, etc.
    most_productive_hour = db.Column(db.Integer)  # 0-23
    average_session_duration = db.Column(db.Float)  # minutes
    research_streak_days = db.Column(db.Integer, default=0)
    last_research_date = db.Column(db.Date)
    
    # Timestamps
    last_updated = db.Column(db.DateTime, default=now_utc)
    
    def __repr__(self):
        return f'<ResearchMetrics for User {self.user_id}>'


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


class ResearchLog(db.Model):
    """
    Detailed log of all research activities for pattern analysis.
    This is the raw data that feeds into aggregated metrics.
    """
    __tablename__ = 'research_log'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # What was done
    activity_type = db.Column(db.String(50), nullable=False)
    # Types: 'idea_captured', 'idea_killed', 'idea_promoted', 'research_started',
    # 'step_completed', 'decision_made', 'thesis_updated', 'document_uploaded', etc.
    
    # Associated entities
    idea_id = db.Column(db.Integer, db.ForeignKey('idea_pipeline.id', ondelete='CASCADE'))
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'))
    project_id = db.Column(db.Integer, db.ForeignKey('research_project.id', ondelete='CASCADE'))
    
    # Activity details
    details = db.Column(db.JSON)  # Flexible field for activity-specific data
    duration_minutes = db.Column(db.Integer)
    
    # When it happened
    timestamp = db.Column(db.DateTime, default=now_utc, index=True)
    day_of_week = db.Column(db.Integer)  # 0=Monday, 6=Sunday
    hour_of_day = db.Column(db.Integer)  # 0-23
    
    def __repr__(self):
        return f'<ResearchLog {self.activity_type} at {self.timestamp}>'


class DecisionJournal(db.Model):
    """
    Track investment decisions with pre-mortem and post-mortem analysis.
    This helps investors learn from both good and bad decisions.
    """
    __tablename__ = 'decision_journal'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('research_project.id'))
    
    # Decision details
    decision_type = db.Column(db.String(20), nullable=False)  # 'invest', 'pass', 'exit'
    decision_date = db.Column(db.Date, nullable=False)
    confidence_score = db.Column(db.Integer)  # 1-10
    
    # Pre-mortem (filled when making decision)
    investment_thesis = db.Column(db.Text)
    expected_return = db.Column(db.Float)  # Percentage
    expected_timeframe = db.Column(db.Integer)  # Months
    key_assumptions = db.Column(db.JSON)  # List of assumptions
    biggest_risks = db.Column(db.JSON)  # List of risks
    exit_criteria = db.Column(db.Text)  # What would make you sell?
    
    # Post-mortem (filled later)
    actual_return = db.Column(db.Float)
    actual_timeframe = db.Column(db.Integer)  # Months
    outcome_date = db.Column(db.Date)
    outcome_notes = db.Column(db.Text)
    
    # Learning
    what_went_right = db.Column(db.Text)
    what_went_wrong = db.Column(db.Text)
    lessons_learned = db.Column(db.Text)
    would_repeat = db.Column(db.Boolean)
    
    # Categorization for pattern analysis
    mistake_category = db.Column(db.String(100))  # 'valuation', 'thesis_wrong', 'timing', etc.
    success_category = db.Column(db.String(100))  # 'thesis_correct', 'patience', 'contrarian', etc.
    
    created_at = db.Column(db.DateTime, default=now_utc)
    updated_at = db.Column(db.DateTime, default=now_utc, onupdate=now_utc)
    
    def __repr__(self):
        return f'<DecisionJournal {self.decision_type} for Company {self.company_id}>'    
    

class JournalEntry(db.Model):
    """
    Enhanced journal entries that capture investment thinking over time.
    These are more structured than simple notes, designed to build knowledge.
    """
    __tablename__ = 'journal_entry'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Entry metadata
    title = db.Column(db.String(200))
    entry_type = db.Column(db.String(50), nullable=False, default='observation')
    # Types: 'observation', 'thesis_update', 'question', 'insight', 'lesson_learned', 
    # 'market_thought', 'meeting_notes', 'earnings_reaction', 'news_analysis'
    
    # Content
    content = db.Column(db.Text, nullable=False)
    
    # Structured elements (optional)
    key_insight = db.Column(db.Text)  # The main takeaway
    action_items = db.Column(db.JSON)  # List of follow-up actions
    questions_raised = db.Column(db.JSON)  # Questions to investigate
    
    # Mood/Sentiment tracking
    sentiment = db.Column(db.String(20))  # 'bullish', 'bearish', 'neutral', 'uncertain'
    conviction_level = db.Column(db.Integer)  # 1-10 scale
    
    # Associations
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'))
    project_id = db.Column(db.Integer, db.ForeignKey('research_project.id'))
    idea_id = db.Column(db.Integer, db.ForeignKey('idea_pipeline.id'))
    
    # Tags for categorization and search
    tags = db.Column(db.JSON, default=list)
    
    # Source/Context
    source = db.Column(db.String(200))  # 'earnings_call', 'article', 'conversation', etc.
    source_url = db.Column(db.String(500))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=now_utc, index=True)
    updated_at = db.Column(db.DateTime, default=now_utc, onupdate=now_utc)
    
    # Review tracking
    last_reviewed = db.Column(db.DateTime)
    review_count = db.Column(db.Integer, default=0)
    review_notes = db.Column(db.Text)  # Notes added during review process
    is_starred = db.Column(db.Boolean, default=False)
    is_archived = db.Column(db.Boolean, default=False)
    
    # AI Intelligence fields
    ai_analysis_result = db.Column(db.JSON)  # Full AI analysis results
    ai_analyzed_at = db.Column(db.DateTime)  # When AI analysis was performed
    ai_confidence_score = db.Column(db.Float)  # AI confidence in analysis (0-1)

    # Intelligent tagging and theme extraction
    ai_suggested_tags = db.Column(db.JSON)  # AI-suggested tags for this entry
    ai_themes_extracted = db.Column(db.JSON)  # AI-extracted themes and insights

    # Connection tracking
    related_entry_ids = db.Column(db.JSON)  # IDs of related entries found by AI
    contradiction_flags = db.Column(db.JSON)  # Detected thesis contradictions

    # Processing status for AI features
    ai_processing_status = db.Column(db.String(50))  # 'pending', 'processing', 'completed', 'failed', 'skipped'

    # Relationships
    company = db.relationship('Company', backref='journal_entries')
    attachments = db.relationship('JournalAttachment', backref='entry',
                                 lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<JournalEntry {self.title or self.id}>'


class JournalAttachment(db.Model):
    """
    Attachments for journal entries - images, charts, documents.
    """
    __tablename__ = 'journal_attachment'
    
    id = db.Column(db.Integer, primary_key=True)
    journal_entry_id = db.Column(db.Integer, db.ForeignKey('journal_entry.id'), nullable=False)
    
    filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(50))  # 'image', 'pdf', 'spreadsheet', etc.
    file_path = db.Column(db.String(500))
    file_size = db.Column(db.Integer)  # In bytes
    
    caption = db.Column(db.Text)
    
    uploaded_at = db.Column(db.DateTime, default=now_utc)
    
    def __repr__(self):
        return f'<JournalAttachment {self.filename}>'


class ThesisEvolution(db.Model):
    """
    Track how investment theses change over time.
    This helps identify pattern recognition and decision evolution.
    """
    __tablename__ = 'thesis_evolution'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    
    # Thesis version
    version = db.Column(db.Integer, default=1)
    thesis = db.Column(db.Text, nullable=False)
    
    # What changed from previous version
    change_summary = db.Column(db.Text)
    change_trigger = db.Column(db.String(200))  # What caused the update
    
    # Conviction tracking
    conviction_level = db.Column(db.Integer)  # 1-10
    position_sizing = db.Column(db.String(50))  # 'starter', 'half', 'full', 'oversized'
    
    # Key factors at this point
    bull_case = db.Column(db.JSON)  # List of bullish points
    bear_case = db.Column(db.JSON)  # List of bearish points
    key_metrics = db.Column(db.JSON)  # Important metrics at this time
    
    # Status
    is_current = db.Column(db.Boolean, default=True)
    
    created_at = db.Column(db.DateTime, default=now_utc)
    
    # Relationships
    company = db.relationship('Company', backref='thesis_versions')
    linked_journal_entry_id = db.Column(db.Integer, db.ForeignKey('journal_entry.id'))
    
    def __repr__(self):
        return f'<ThesisEvolution v{self.version} for Company {self.company_id}>'


class LearningNote(db.Model):
    """
    Structured learning notes that capture investment lessons.
    These are meant to be reviewed and internalized over time.
    """
    __tablename__ = 'learning_note'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Learning content
    title = db.Column(db.String(200), nullable=False)
    lesson = db.Column(db.Text, nullable=False)
    
    # Categorization
    category = db.Column(db.String(100))  # 'mistake', 'success', 'process', 'market_wisdom'
    subcategory = db.Column(db.String(100))  # More specific classification
    
    # Context
    context = db.Column(db.Text)  # The situation that led to this learning
    
    # Application
    how_to_apply = db.Column(db.Text)  # How to use this lesson in future
    
    # Examples
    examples = db.Column(db.JSON)  # Specific examples of this lesson
    anti_examples = db.Column(db.JSON)  # Counter-examples
    
    # Source
    source_type = db.Column(db.String(50))  # 'experience', 'book', 'mentor', 'article'
    source_detail = db.Column(db.String(200))
    
    # Related entities
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'))
    decision_id = db.Column(db.Integer, db.ForeignKey('decision_journal.id'))
    
    # Review and reinforcement
    times_reviewed = db.Column(db.Integer, default=0)
    last_reviewed = db.Column(db.DateTime)
    importance = db.Column(db.Integer, default=5)  # 1-10 scale
    
    # Spaced repetition
    next_review_date = db.Column(db.Date)
    review_interval_days = db.Column(db.Integer, default=7)
    
    created_at = db.Column(db.DateTime, default=now_utc)
    updated_at = db.Column(db.DateTime, default=now_utc, onupdate=now_utc)
    
    # Tags for cross-referencing
    tags = db.Column(db.JSON, default=list)
    
    def __repr__(self):
        return f'<LearningNote {self.title}>'


class JournalTemplate(db.Model):
    """
    Templates for different types of journal entries to ensure consistency.
    """
    __tablename__ = 'journal_template'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Null for system templates
    
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    entry_type = db.Column(db.String(50), nullable=False)
    
    # Template structure
    prompts = db.Column(db.JSON)  # List of questions/prompts to answer
    required_fields = db.Column(db.JSON)  # Fields that must be filled
    
    # Example content
    example_content = db.Column(db.Text)
    
    is_active = db.Column(db.Boolean, default=True)
    is_public = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=now_utc)
    
    def __repr__(self):
        return f'<JournalTemplate {self.name}>'
    
# Add these new models to app/models.py

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


class WeeklyReview(db.Model):
    """
    Structured weekly reviews to maintain learning momentum.
    """
    __tablename__ = 'weekly_review'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    week_start = db.Column(db.Date, nullable=False)
    week_end = db.Column(db.Date, nullable=False)
    
    # Activities summary
    ideas_captured = db.Column(db.Integer, default=0)
    ideas_killed = db.Column(db.Integer, default=0)
    research_hours = db.Column(db.Float, default=0)
    decisions_made = db.Column(db.Integer, default=0)
    
    # Reflections
    biggest_win = db.Column(db.Text)
    biggest_challenge = db.Column(db.Text)
    key_learnings = db.Column(db.JSON)  # List of learnings
    
    # Market observations
    market_thoughts = db.Column(db.Text)
    opportunities_identified = db.Column(db.JSON)  # List of opportunities
    risks_identified = db.Column(db.JSON)  # List of risks
    
    # Planning
    next_week_priorities = db.Column(db.JSON)  # List of priorities
    companies_to_research = db.Column(db.JSON)  # List of company IDs or names
    
    # Accountability
    last_week_goals_achieved = db.Column(db.JSON)  # What was accomplished
    goals_completion_rate = db.Column(db.Integer)  # Percentage
    
    # Sentiment tracking
    confidence_level = db.Column(db.Integer)  # 1-10
    market_sentiment = db.Column(db.String(50))  # 'bullish', 'bearish', 'neutral'
    
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=now_utc)
    
    def __repr__(self):
        return f'<WeeklyReview {self.week_start}>'


class InvestmentPostMortem(db.Model):
    """
    Detailed post-mortem analysis of completed investments.
    """
    __tablename__ = 'investment_postmortem'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    decision_id = db.Column(db.Integer, db.ForeignKey('decision_journal.id'))
    
    # Investment details
    entry_date = db.Column(db.Date, nullable=False)
    exit_date = db.Column(db.Date, nullable=False)
    holding_period_days = db.Column(db.Integer)
    
    # Performance
    entry_price = db.Column(db.Float)
    exit_price = db.Column(db.Float)
    total_return = db.Column(db.Float)  # Percentage
    annualized_return = db.Column(db.Float)
    
    # vs Benchmark
    benchmark_return = db.Column(db.Float)  # S&P 500 or relevant benchmark
    alpha = db.Column(db.Float)  # Excess return
    
    # Analysis
    outcome = db.Column(db.String(50))  # 'success', 'failure', 'mixed'
    
    # What happened
    thesis_accuracy = db.Column(db.String(50))  # 'correct', 'partially_correct', 'wrong'
    thesis_playing_out = db.Column(db.Text)  # How the thesis played out
    unexpected_developments = db.Column(db.JSON)  # List of surprises
    
    # Decision quality analysis
    decision_quality_score = db.Column(db.Integer)  # 1-10
    process_followed = db.Column(db.Boolean)
    emotional_factors = db.Column(db.Text)
    
    # Learnings
    what_went_well = db.Column(db.JSON)  # List of positives
    what_went_poorly = db.Column(db.JSON)  # List of negatives
    lucky_breaks = db.Column(db.JSON)  # Acknowledge luck
    
    # Key lessons
    primary_lesson = db.Column(db.Text)
    secondary_lessons = db.Column(db.JSON)
    
    # Process improvements
    process_improvements = db.Column(db.JSON)  # Changes to make
    would_repeat = db.Column(db.Boolean)
    
    # Supporting documents
    attachments = db.Column(db.JSON)  # Links or filenames
    
    created_at = db.Column(db.DateTime, default=now_utc)
    
    # Relationships
    company = db.relationship('Company', backref='postmortems')
    decision = db.relationship('DecisionJournal', backref='postmortem')
    
    def __repr__(self):
        return f'<InvestmentPostMortem {self.company_id}>'


class LearningPath(db.Model):
    """
    Structured learning paths for improving specific skills.
    """
    __tablename__ = 'learning_path'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    skill_area = db.Column(db.String(100))  # 'valuation', 'industry_analysis', etc.
    
    # Path structure
    total_steps = db.Column(db.Integer)
    completed_steps = db.Column(db.Integer, default=0)
    
    # Content
    learning_resources = db.Column(db.JSON)  # Books, courses, articles
    practice_exercises = db.Column(db.JSON)  # Practical exercises
    milestones = db.Column(db.JSON)  # Key milestones to achieve
    
    # Progress tracking
    current_step = db.Column(db.Integer, default=1)
    progress_notes = db.Column(db.JSON)  # Notes for each step
    
    # Completion
    started_at = db.Column(db.DateTime)
    target_completion = db.Column(db.Date)
    completed_at = db.Column(db.DateTime)
    
    status = db.Column(db.String(50), default='planned')  # 'planned', 'active', 'completed', 'paused'
    
    created_at = db.Column(db.DateTime, default=now_utc)
    
    def __repr__(self):
        return f'<LearningPath {self.name}>'


class PatternRecognition(db.Model):
    """
    Identified patterns in investment behavior and outcomes.
    """
    __tablename__ = 'pattern_recognition'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    pattern_name = db.Column(db.String(200), nullable=False)
    pattern_type = db.Column(db.String(100))  # 'success_pattern', 'failure_pattern', 'behavioral'
    
    description = db.Column(db.Text, nullable=False)
    
    # Evidence
    occurrences = db.Column(db.Integer, default=1)
    examples = db.Column(db.JSON)  # List of specific examples
    
    # Impact
    impact_score = db.Column(db.Integer)  # 1-10
    financial_impact = db.Column(db.Text)  # Estimated financial impact
    
    # Action plan
    how_to_leverage = db.Column(db.Text)  # For success patterns
    how_to_avoid = db.Column(db.Text)  # For failure patterns
    
    # Validation
    confidence_level = db.Column(db.Integer)  # 1-10
    needs_more_data = db.Column(db.Boolean, default=False)
    
    identified_date = db.Column(db.Date, default=now_utc().date)
    last_observed = db.Column(db.Date)
    
    created_at = db.Column(db.DateTime, default=now_utc)
    
    def __repr__(self):
        return f'<PatternRecognition {self.pattern_name}>'


class DocumentImport(db.Model):
    """
    Track document imports for checklist creation
    """
    __tablename__ = 'document_imports'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # File information
    filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(50), nullable=False)  # pdf, docx, txt
    file_size = db.Column(db.Integer)  # Size in bytes
    file_path = db.Column(db.String(500))  # Stored file path

    # Processing information
    status = db.Column(db.String(50), default='uploaded')  # uploaded, processing, completed, failed
    llm_provider = db.Column(db.String(50))  # openai, gemini
    processing_approach = db.Column(db.String(50))  # immediate, interactive

    # Extracted content
    raw_text = db.Column(db.Text)
    processed_items = db.Column(db.JSON)  # Structured checklist items from LLM

    # Results
    suggested_name = db.Column(db.String(200))
    suggested_description = db.Column(db.Text)
    created_checklist_id = db.Column(db.Integer, db.ForeignKey('checklist.id'))

    # Metadata
    processing_time = db.Column(db.Float)  # Processing time in seconds
    error_message = db.Column(db.Text)

    # Timestamps
    created_at = db.Column(db.DateTime, default=now_utc)
    processed_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)

    # Relationships
    user = db.relationship('User', backref='document_imports')
    created_checklist = db.relationship('Checklist', backref='document_import', uselist=False)

    def __repr__(self):
        return f'<DocumentImport {self.filename} - {self.status}>'


class OnboardingProgress(db.Model):
    """
    Track detailed onboarding progress and user's first experience
    """
    __tablename__ = 'onboarding_progress'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Step tracking
    current_step = db.Column(db.Integer, default=0)
    completed_steps = db.Column(db.JSON, default=[])  # List of completed step numbers

    # First experience data
    first_company_name = db.Column(db.String(200))  # Their first company idea
    first_company_id = db.Column(db.Integer, db.ForeignKey('company.id', ondelete='SET NULL'))
    first_kill_checklist_id = db.Column(db.Integer, db.ForeignKey('kill_checklist.id', ondelete='SET NULL'))
    first_research_template_id = db.Column(db.Integer, db.ForeignKey('research_template.id', ondelete='SET NULL'))
    first_research_project_id = db.Column(db.Integer, db.ForeignKey('research_project.id', ondelete='SET NULL'))

    # Timing
    step_start_times = db.Column(db.JSON, default={})  # Track time spent on each step
    step_completion_times = db.Column(db.JSON, default={})

    # Feedback
    onboarding_feedback = db.Column(db.Text)
    satisfaction_score = db.Column(db.Integer)  # 1-10

    # Research data from onboarding session
    onboarding_research_answers = db.Column(db.JSON)  # Raw answers from Step 5
    onboarding_structured_answers = db.Column(db.JSON)  # Structured Q&A pairs

    # Step 5 confirmation
    checklist_confirmed = db.Column(db.Boolean, default=False)
    checklist_confirmation_time = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=now_utc)
    completed_at = db.Column(db.DateTime)

    # Relationships
    user = db.relationship('User', backref='onboarding_progress')
    first_company = db.relationship('Company', foreign_keys=[first_company_id])
    first_kill_checklist = db.relationship('KillChecklist', foreign_keys=[first_kill_checklist_id])
    first_research_template = db.relationship('ResearchTemplate', foreign_keys=[first_research_template_id])
    first_research_project = db.relationship('ResearchProject', foreign_keys=[first_research_project_id])

    def __repr__(self):
        return f'<OnboardingProgress User:{self.user_id} Step:{self.current_step}>'