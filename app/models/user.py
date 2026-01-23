# app/models/user.py

from app import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from .associations import favorite_companies
from app.utils.time_utils import now_utc, ensure_timezone_aware
from datetime import timedelta


# The User class needs to inherit from UserMixin
class User(UserMixin, db.Model):  # Add UserMixin here
    id = db.Column(db.Integer, primary_key=True)

    # Auth0 Integration
    auth0_id = db.Column(db.String(255), unique=True, nullable=True, index=True)
    # Auth0 user ID (e.g., "auth0|123456", "google-oauth2|123456")

    # Traditional auth fields (nullable for OAuth-only users)
    username = db.Column(db.String(64), index=True, unique=True, nullable=True)
    email = db.Column(db.String(120), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=True)

    # Auth0 profile data
    name = db.Column(db.String(200), nullable=True)  # Full name from Auth0
    picture = db.Column(db.String(500), nullable=True)  # Profile picture URL from Auth0
    auth_provider = db.Column(db.String(50), nullable=True)  # 'auth0', 'google', 'github', etc.
    uploaded_documents = db.relationship(
        "CompanyDocument", backref="uploader", lazy="dynamic"
    )
    checklists = db.relationship("Checklist", backref="author", lazy="dynamic")
    research_sessions = db.relationship(
        "ChecklistAnalysis", backref="researcher", lazy="dynamic"
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

    # AI Token Usage Tracking
    ai_tokens_used = db.Column(db.Integer, nullable=False, default=0, index=True)
    ai_tokens_limit = db.Column(db.Integer, nullable=False, default=10000)  # Free tier default
    ai_tokens_reset_date = db.Column(db.DateTime, nullable=True)

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

    # User preferences
    preferred_sprint_duration = db.Column(db.Integer, default=30)  # minutes
    research_experience_level = db.Column(db.String(20), default='intermediate')  # beginner, intermediate, expert
    notification_preferences = db.Column(db.JSON, default={'pattern_alerts': True, 'weekly_review': True, 'fomo_alerts': True})

    # MULTI-CURRENCY SUPPORT
    base_currency = db.Column(db.String(3), nullable=False, default='USD')  # User's preferred reporting currency
    show_original_currency = db.Column(db.Boolean, default=True)  # Show both original and base currency

    # Community features
    buddy_system_enabled = db.Column(db.Boolean, default=False)

    # FOMO protection
    last_fomo_alert = db.Column(db.DateTime)
    fomo_protection_level = db.Column(db.String(20), default='medium')  # low, medium, high

    # Onboarding and tour tracking
    onboarding_completed = db.Column(db.Boolean, default=False)
    onboarding_path_chosen = db.Column(db.String(20))  # 'company' or 'sector'
    onboarding_completed_at = db.Column(db.DateTime)
    page_tours_completed = db.Column(db.JSON, default={})  # {'dashboard': True, 'inbox': False, ...}
    tour_preferences = db.Column(db.JSON, default={'show_page_tours': True})

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        # Ensure password_hash is not None before checking
        if self.password_hash is None:
            return False
        return check_password_hash(self.password_hash, password)

    # AI Token Management Methods
    def check_and_reset_tokens(self):
        """Check if token reset date has passed and reset if needed."""
        if self.ai_tokens_reset_date is None:
            # First time using AI - set reset date to 30 days from now
            self.ai_tokens_reset_date = now_utc() + timedelta(days=30)
            return

        # Ensure reset_date is timezone-aware for comparison
        reset_date_aware = ensure_timezone_aware(self.ai_tokens_reset_date)

        if now_utc() >= reset_date_aware:
            # Reset period has passed - reset tokens
            self.ai_tokens_used = 0
            self.ai_tokens_reset_date = now_utc() + timedelta(days=30)
            db.session.commit()

    def can_use_ai_tokens(self, tokens_needed=5000):
        """
        Check if user has enough tokens available.

        Args:
            tokens_needed: Number of tokens needed (default 5000 for research assistant)

        Returns:
            bool: True if user has enough tokens, False otherwise
        """
        self.check_and_reset_tokens()
        return (self.ai_tokens_used + tokens_needed) <= self.ai_tokens_limit

    def increment_ai_tokens(self, tokens_used):
        """
        Increment user's AI token usage counter.

        Args:
            tokens_used: Number of tokens consumed by the AI request
        """
        self.ai_tokens_used += tokens_used
        db.session.commit()

    def get_token_usage_percentage(self):
        """
        Calculate token usage as percentage for UI display.

        Returns:
            float: Percentage of tokens used (0-100)
        """
        if self.ai_tokens_limit == 0:
            return 0.0
        return (self.ai_tokens_used / self.ai_tokens_limit) * 100

    def get_tokens_remaining(self):
        """
        Get number of tokens remaining in current period.

        Returns:
            int: Tokens remaining
        """
        return max(0, self.ai_tokens_limit - self.ai_tokens_used)

    def __repr__(self):
        return f"<User {self.username}>"
