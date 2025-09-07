# company_research_platform/app/models.py

from app import db  # Import the db instance from app/__init__.py
from datetime import datetime
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
    mistake_logs = db.relationship(
        "MistakeLog", backref="author", lazy="dynamic", cascade="all, delete-orphan"
    )
    subscription_tier = db.Column(db.String(50), nullable=False, default="free")
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
    description = db.Column(db.String(300))
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
    documents = db.relationship(
        "CompanyDocument",
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
    journal_entries = db.relationship(
        "JournalEntry", backref="company", lazy="dynamic", cascade="all, delete-orphan"
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
    start_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
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
    answered_at = db.Column(db.DateTime, default=datetime.utcnow)
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
    uploaded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

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

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

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
    fetched_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

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
        db.DateTime, nullable=False, default=datetime.utcnow, index=True
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

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Ensure a user can only have one of each analysis type per company
    __table_args__ = (
        db.UniqueConstraint(
            "company_id", "user_id", "model_type", name="uq_user_company_analysis"
        ),
    )

    def __repr__(self):
        return f"<QualitativeAnalysis {self.model_type} for Company {self.company_id}>"


class MistakeLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    # A description of the investment mistake
    mistake_description = db.Column(db.Text, nullable=False)

    # The source of the lesson (e.g., "Personal", "Warren Buffett", "Peter Lynch")
    source = db.Column(db.String(150), nullable=True)

    # The actionable lesson learned from the mistake
    lesson_learned = db.Column(db.Text, nullable=False)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<MistakeLog {self.id} by User {self.user_id}>"


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

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<QuestionBankItem {self.text[:50]}...>"


class SectorAnalysis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    # The name of the sector being analyzed
    sector_name = db.Column(db.String(100), nullable=False, index=True)

    # A large text field for free-form research notes
    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Ensure a user can only have one analysis notebook per sector name
    __table_args__ = (
        db.UniqueConstraint("user_id", "sector_name", name="uq_user_sector"),
    )

    def __repr__(self):
        return f'<SectorAnalysis for "{self.sector_name}" by User {self.user_id}>'


class JournalEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=True)

    # Optional: Tags for categorizing entries, like "Competitor Analysis", "Red Flag"
    tags = db.Column(db.String(200), nullable=True)

    entry_date = db.Column(db.DateTime, index=True, default=datetime.utcnow)

    def __repr__(self):
        return f'<JournalEntry "{self.title}">'


class IdeaPipeline(db.Model):
    __tablename__ = 'idea_pipeline'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    idea_type = db.Column(db.String(50), nullable=False, default='company')
    ticker_symbol = db.Column(db.String(20))
    source = db.Column(db.String(200))
    thesis_summary = db.Column(db.Text)
    initial_notes = db.Column(db.Text)
    status = db.Column(db.String(50), default='inbox', index=True)
    kill_reason = db.Column(db.Text)
    failed_criterion_id = db.Column(db.Integer, db.ForeignKey('kill_criterion.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    killed_at = db.Column(db.DateTime)
    promoted_at = db.Column(db.DateTime)
    last_reviewed_at = db.Column(db.DateTime)
    priority = db.Column(db.Integer, default=0)
    promoted_to_company_id = db.Column(db.Integer, db.ForeignKey('company.id'))
    kill_sessions = db.relationship('KillSession', backref='idea', lazy='dynamic', cascade='all, delete-orphan')
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    killed_ideas = db.relationship('IdeaPipeline', backref='failed_criterion', foreign_keys='IdeaPipeline.failed_criterion_id')

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
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
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
    answered_at = db.Column(db.DateTime, default=datetime.utcnow)
    criterion = db.relationship('KillCriterion')

    def __repr__(self):
        return f'<KillAnswer {self.passed}>'
    

# app/ideas/routes.py

from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user, login_required
from app import db
from app.models import (IdeaPipeline, KillChecklist, KillCriterion,
                       KillSession, KillAnswer, Company)
from app.ideas import ideas_bp
from datetime import datetime, timedelta
from app.companies.routes import EXCHANGES # Import EXCHANGES dictionary

@ideas_bp.route('/inbox')
@login_required
def inbox():
    """Display the user's idea inbox - ideas waiting to be evaluated"""
    # Query for ideas that are in the inbox or survived but have not been promoted
    ideas = IdeaPipeline.query.filter(
        IdeaPipeline.user_id == current_user.id,
        IdeaPipeline.status.in_(['inbox', 'survived'])
    ).order_by(IdeaPipeline.created_at.desc()).all()
    
    default_kill_checklist = KillChecklist.query.filter_by(
        user_id=current_user.id, 
        is_default=True
    ).first()
    
    return render_template('inbox.html', 
                          title="Idea Inbox",
                          ideas=ideas,
                          default_kill_checklist=default_kill_checklist,
                          now=datetime.utcnow()
                          )

@ideas_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_idea():
    """Quick capture for new ideas"""
    if request.method == 'POST':
        name = request.form.get('name')
        idea_type = request.form.get('idea_type', 'company')
        base_ticker = request.form.get('base_ticker', '').upper()
        exchange_suffix = request.form.get('exchange_suffix', '')
        full_ticker = f"{base_ticker}{exchange_suffix}" if base_ticker else None
        source = request.form.get('source')
        thesis = request.form.get('thesis_summary')
        notes = request.form.get('initial_notes')
        
        if not name:
            flash('Idea name is required', 'error')
            return redirect(url_for('ideas.add_idea'))
        
        new_idea = IdeaPipeline(
            author=current_user, name=name, idea_type=idea_type,
            ticker_symbol=full_ticker, source=source, thesis_summary=thesis,
            initial_notes=notes, status='inbox'
        )
        
        try:
            db.session.add(new_idea)
            db.session.commit()
            flash(f'"{name}" added to your idea inbox!', 'success')
            return redirect(url_for('ideas.inbox'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding idea: {str(e)}', 'error')
    
    return render_template('add_idea.html', title="Quick Capture", exchanges=EXCHANGES)

@ideas_bp.route('/<int:idea_id>/kill', methods=['GET', 'POST'])
@login_required
def kill_room(idea_id):
    """The kill room - evaluate an idea against kill criteria"""
    idea = IdeaPipeline.query.get_or_404(idea_id)

    if idea.user_id != current_user.id:
        flash('You do not have access to this idea', 'error')
        return redirect(url_for('ideas.inbox'))

    kill_session = KillSession.query.filter_by(
        user_id=current_user.id, idea_id=idea.id, outcome=None
    ).first()

    if not kill_session:
        kill_checklist = KillChecklist.query.filter_by(user_id=current_user.id, is_default=True).first()
        if not kill_checklist:
            flash('Please create a kill checklist first', 'warning')
            return redirect(url_for('ideas.create_kill_checklist'))
        kill_session = KillSession(user_id=current_user.id, idea=idea, checklist=kill_checklist)
        db.session.add(kill_session)
        idea.status = 'killing'
        db.session.commit()

    criteria = kill_session.checklist.criteria.order_by(KillCriterion.order).all()
    existing_answers = {ans.criterion_id: ans for ans in kill_session.answers.all()}
    
    current_criterion = None
    current_index = 0
    for i, criterion in enumerate(criteria):
        if criterion.id not in existing_answers:
            current_criterion = criterion
            current_index = i
            break

    if request.method == 'POST' and current_criterion:
        passed = request.form.get('passed') == 'true'
        notes = request.form.get('notes', '')
        answer = KillAnswer(session=kill_session, criterion=current_criterion, passed=passed, notes=notes)
        db.session.add(answer)
        current_criterion.times_evaluated += 1
        
        if not passed:
            current_criterion.times_failed += 1
            idea.status = 'killed'
            idea.kill_reason = current_criterion.question
            idea.failed_criterion = current_criterion
            idea.killed_at = datetime.utcnow()
            kill_session.outcome = 'killed'
            kill_session.completed_at = datetime.utcnow()
            kill_session.checklist.total_ideas_evaluated += 1
            kill_session.checklist.total_ideas_killed += 1
            db.session.commit()
            flash(f'"{idea.name}" has been killed. Reason: {current_criterion.question}', 'info')
            return redirect(url_for('ideas.graveyard'))

        db.session.commit()

        if current_index == len(criteria) - 1:
            idea.status = 'survived'
            idea.promoted_at = datetime.utcnow()
            kill_session.outcome = 'survived'
            kill_session.completed_at = datetime.utcnow()
            kill_session.checklist.total_ideas_evaluated += 1
            db.session.commit()
            
            if idea.ticker_symbol:
                flash(f'🎉 "{idea.name}" survived the kill checklist! Ready for promotion.', 'success')
                return redirect(url_for('ideas.promote_to_company', idea_id=idea.id))
            else:
                flash(f'🎉 Idea "{idea.name}" survived the kill checklist!', 'success')
                return redirect(url_for('ideas.inbox'))
        
        return redirect(url_for('ideas.kill_room', idea_id=idea.id))

    progress_percent = (len(existing_answers) / len(criteria)) * 100 if criteria else 0
    return render_template('kill_room.html', title=f"Kill Room: {idea.name}", idea=idea,
                           session=kill_session, current_criterion=current_criterion,
                           current_index=current_index, total_criteria=len(criteria),
                           progress_percent=progress_percent, existing_answers=existing_answers)

@ideas_bp.route('/graveyard')
@login_required
def graveyard():
    killed_ideas = current_user.idea_pipeline.filter_by(status='killed').order_by(IdeaPipeline.killed_at.desc()).all()
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    recent_kill_count = sum(1 for idea in killed_ideas if idea.killed_at and idea.killed_at > thirty_days_ago)
    kill_reasons = {}
    for idea in killed_ideas:
        reason = idea.kill_reason or "Unknown"
        if reason not in kill_reasons:
            kill_reasons[reason] = []
        kill_reasons[reason].append(idea)
    return render_template('graveyard.html', title="Idea Graveyard", killed_ideas=killed_ideas,
                           kill_reasons=kill_reasons, recent_kill_count=recent_kill_count)

@ideas_bp.route('/kill-checklists')
@login_required
def manage_kill_checklists():
    checklists = current_user.kill_checklists.all()
    return render_template('manage_kill_checklists.html', title="Kill Checklists", checklists=checklists)

@ideas_bp.route('/kill-checklists/new', methods=['GET', 'POST'])
@login_required
def create_kill_checklist():
    if request.method == 'POST':
        name = request.form.get('name')
        if not name:
            flash('Checklist name is required', 'error')
            return redirect(url_for('ideas.create_kill_checklist'))
        
        is_default = request.form.get('is_default') == 'true'
        if is_default:
            KillChecklist.query.filter_by(user_id=current_user.id, is_default=True).update({'is_default': False})
        
        checklist = KillChecklist(
            author=current_user, name=name, description=request.form.get('description'), is_default=is_default
        )
        db.session.add(checklist)
        db.session.flush()
        
        criteria_questions = request.form.getlist('criterion_question[]')
        criteria_reasons = request.form.getlist('criterion_reason[]')
        for i, question in enumerate(criteria_questions):
            if question.strip():
                criterion = KillCriterion(
                    kill_checklist=checklist, question=question.strip(),
                    failure_reason=criteria_reasons[i] if i < len(criteria_reasons) else '', order=i
                )
                db.session.add(criterion)
        
        db.session.commit()
        flash(f'Kill checklist "{name}" created!', 'success')
        return redirect(url_for('ideas.manage_kill_checklists'))
    
    return render_template('create_kill_checklist.html', title="Create Kill Checklist")

@ideas_bp.route('/kill-checklists/<int:checklist_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_kill_checklist(checklist_id):
    checklist = KillChecklist.query.get_or_404(checklist_id)
    if checklist.user_id != current_user.id:
        flash('You do not have permission to edit this checklist.', 'error')
        return redirect(url_for('ideas.manage_kill_checklists'))
    
    if request.method == 'POST':
        checklist.name = request.form.get('name')
        checklist.description = request.form.get('description')
        is_default = request.form.get('is_default') == 'true'
        if is_default and not checklist.is_default:
            KillChecklist.query.filter_by(user_id=current_user.id, is_default=True).update({'is_default': False})
        checklist.is_default = is_default
        
        criteria_ids = request.form.getlist('criterion_id[]')
        criteria_questions = request.form.getlist('criterion_question[]')
        criteria_reasons = request.form.getlist('criterion_reason[]')
        
        existing_criterion_ids = {c.id for c in checklist.criteria}
        submitted_criterion_ids = {int(id) for id in criteria_ids if id}
        ids_to_delete = existing_criterion_ids - submitted_criterion_ids
        if ids_to_delete:
            KillCriterion.query.filter(KillCriterion.id.in_(ids_to_delete)).delete(synchronize_session=False)
        
        for i, question in enumerate(criteria_questions):
            if question.strip():
                criterion_id = criteria_ids[i] if i < len(criteria_ids) and criteria_ids[i] else None
                if criterion_id:
                    criterion = KillCriterion.query.get(criterion_id)
                    criterion.question = question.strip()
                    criterion.failure_reason = criteria_reasons[i] if i < len(criteria_reasons) else ''
                    criterion.order = i
                else:
                    criterion = KillCriterion(
                        kill_checklist=checklist, question=question.strip(),
                        failure_reason=criteria_reasons[i] if i < len(criteria_reasons) else '', order=i
                    )
                    db.session.add(criterion)
        
        db.session.commit()
        flash(f'Kill checklist "{checklist.name}" updated!', 'success')
        return redirect(url_for('ideas.manage_kill_checklists'))
    
    return render_template('edit_kill_checklist.html', title="Edit Kill Checklist", checklist=checklist)

@ideas_bp.route('/kill-checklists/<int:checklist_id>/delete', methods=['POST'])
@login_required
def delete_kill_checklist(checklist_id):
    checklist = KillChecklist.query.get_or_404(checklist_id)
    if checklist.user_id != current_user.id:
        flash('You do not have permission to delete this checklist.', 'error')
        return redirect(url_for('ideas.manage_kill_checklists'))
    
    db.session.delete(checklist)
    db.session.commit()
    flash(f'Kill checklist "{checklist.name}" has been deleted.', 'success')
    return redirect(url_for('ideas.manage_kill_checklists'))

@ideas_bp.route('/<int:idea_id>/promote', methods=['GET', 'POST'])
@login_required
def promote_to_company(idea_id):
    idea = IdeaPipeline.query.get_or_404(idea_id)
    if not idea.ticker_symbol:
        flash(f'Cannot promote "{idea.name}". Only ideas with a ticker symbol can be promoted to a company.', 'error')
        return redirect(url_for('ideas.inbox'))
    if idea.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('ideas.inbox'))
    
    if request.method == 'POST':
        company = Company(
            name=idea.name, ticker_symbol=idea.ticker_symbol,
            creator=current_user, summary=idea.thesis_summary
        )
        db.session.add(company)
        db.session.flush()
        idea.promoted_to_company = company
        idea.status = 'promoted'
        idea.promoted_at = datetime.utcnow()
        db.session.commit()
        flash(f'"{idea.name}" promoted to your companies list! You can now begin deep research.', 'success')
        return redirect(url_for('research.select_checklist_for_company', company_id=company.id))
    
    return render_template('promote_idea.html', title="Promote to Company", idea=idea, datetime=datetime)

@ideas_bp.route('/<int:idea_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_idea(idea_id):
    idea = IdeaPipeline.query.get_or_404(idea_id)
    if idea.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('ideas.inbox'))
    
    if request.method == 'POST':
        idea.name = request.form.get('name', idea.name)
        idea.idea_type = request.form.get('idea_type', idea.idea_type)
        base_ticker = request.form.get('base_ticker', '').upper()
        exchange_suffix = request.form.get('exchange_suffix', '')
        idea.ticker_symbol = f"{base_ticker}{exchange_suffix}" if base_ticker else None
        idea.source = request.form.get('source')
        idea.thesis_summary = request.form.get('thesis_summary')
        idea.initial_notes = request.form.get('initial_notes')
        
        try:
            db.session.commit()
            flash('Idea updated successfully', 'success')
            return redirect(url_for('ideas.inbox'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating idea: {str(e)}', 'error')
            
    base_ticker, exchange_suffix = '', ''
    if idea.ticker_symbol:
        if '.' in idea.ticker_symbol:
            parts = idea.ticker_symbol.rsplit('.', 1)
            base_ticker = parts[0]
            exchange_suffix = '.' + parts[1]
        else:
            base_ticker = idea.ticker_symbol
            
    return render_template('edit_idea.html', title="Edit Idea", idea=idea,
                           exchanges=EXCHANGES, base_ticker=base_ticker, exchange_suffix=exchange_suffix)

@ideas_bp.route('/<int:idea_id>/delete', methods=['POST'])
@login_required
def delete_idea(idea_id):
    idea = IdeaPipeline.query.get_or_404(idea_id)
    if idea.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('ideas.inbox'))
    
    try:
        db.session.delete(idea)
        db.session.commit()
        flash(f'"{idea.name}" deleted permanently', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting idea: {str(e)}', 'error')
    
    return redirect(url_for('ideas.inbox'))

@ideas_bp.route('/<int:idea_id>/resurrect', methods=['POST'])
@login_required
def resurrect_idea(idea_id):
    idea = IdeaPipeline.query.get_or_404(idea_id)
    if idea.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    idea.status = 'inbox'
    idea.kill_reason = None
    idea.failed_criterion_id = None
    idea.killed_at = None
    
    try:
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@ideas_bp.route('/<int:idea_id>/mark_someday', methods=['GET'])
@login_required
def mark_someday(idea_id):
    idea = IdeaPipeline.query.get_or_404(idea_id)
    if idea.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('ideas.inbox'))
    
    idea.status = 'someday'
    idea.last_reviewed_at = datetime.utcnow()
    
    try:
        db.session.commit()
        flash(f'"{idea.name}" moved to Someday/Maybe', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating idea: {str(e)}', 'error')
    
    return redirect(url_for('ideas.inbox'))

@ideas_bp.route('/kill-checklists/<int:checklist_id>/set-default', methods=['POST'])
@login_required
def set_default_checklist(checklist_id):
    checklist = KillChecklist.query.get_or_404(checklist_id)
    if checklist.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('ideas.manage_kill_checklists'))
    
    KillChecklist.query.filter_by(user_id=current_user.id, is_default=True).update({'is_default': False})
    checklist.is_default = True
    
    try:
        db.session.commit()
        flash(f'"{checklist.name}" set as default kill checklist', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating checklist: {str(e)}', 'error')
    
    return redirect(url_for('ideas.manage_kill_checklists'))

@ideas_bp.route('/<int:idea_id>/details')
@login_required
def idea_details(idea_id):
    idea = IdeaPipeline.query.get_or_404(idea_id)
    if idea.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('ideas.inbox'))
    return redirect(url_for('ideas.edit_idea', idea_id=idea.id))