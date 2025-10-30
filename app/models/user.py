# app/models/user.py

from app import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from .associations import favorite_companies


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

    def __repr__(self):
        return f"<User {self.username}>"
