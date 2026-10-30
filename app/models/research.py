# StartWithA
# Copyright (C) 2024-2026 Kiran Mathews
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

# app/models/research.py

from app import db
from app.utils.time_utils import now_utc, ensure_timezone_aware
from app.utils.blocknote_utils import blocknote_to_text

# Values the app writes to ResearchProject. 'paused' was migrated to 'active'
# (add_circle_of_competence_and_too_hard_fields) and is no longer written.
RESEARCH_PROJECT_STATUSES = ('active', 'completed', 'killed')
RESEARCH_DECISIONS = ('invest', 'pass', 'watchlist')
WATCH_REASONS = ('valuation_too_high', 'waiting_for_catalyst', 'lower_priority', 'other')


class ChecklistAnalysis(db.Model):
    """
    A checklist analysis session tracks the process of analyzing a company
    using a specific checklist. This is used as a step within research workflows.
    """
    __tablename__ = 'checklist_analysis'

    id = db.Column(db.Integer, primary_key=True)
    start_date = db.Column(db.DateTime, nullable=False, default=now_utc)
    status = db.Column(db.String(50), nullable=False, default="in_progress")

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False, index=True)
    checklist_id = db.Column(db.Integer, db.ForeignKey("checklist.id"), nullable=False, index=True)
    conclusion = db.Column(db.Text, nullable=True)

    # Relationships
    checklist = db.relationship("Checklist")

    answers = db.relationship(
        "ChecklistAnswer",
        backref="analysis",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<ChecklistAnalysis {self.id} for Company {self.company_id} using Checklist {self.checklist_id}>"


class ChecklistAnswer(db.Model):
    """
    An answer to a specific checklist item during a checklist analysis.
    """
    __tablename__ = 'checklist_answer'

    id = db.Column(db.Integer, primary_key=True)
    answer_text = db.Column(db.Text, nullable=True)
    answered_at = db.Column(db.DateTime, default=now_utc)
    satisfaction_status = db.Column(db.String(30), nullable=True, default=None)

    checklist_analysis_id = db.Column(
        db.Integer, db.ForeignKey("checklist_analysis.id"), nullable=False, index=True
    )
    checklist_item_id = db.Column(
        db.Integer, db.ForeignKey("checklist_item.id"), nullable=False, index=True
    )

    # Relationship to the specific checklist item
    item = db.relationship("ChecklistItem")

    def __repr__(self):
        return f"<ChecklistAnswer {self.id} for Item {self.checklist_item_id} in Analysis {self.checklist_analysis_id}>"


class ResearchTemplate(db.Model):
    """
    A research template is a reusable workflow that defines how an investor
    analyzes COMPANIES. Think of it as a 'recipe' for systematic company research
    that ensures consistency while allowing flexibility for different investment styles.

    Note: Sector research uses a separate free-form notebook approach (SectorAnalysis model).
    Templates are ONLY for company analysis.
    """
    __tablename__ = 'research_template'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)

    # Basic template information
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    investment_style = db.Column(db.String(100))  # 'value', 'growth', 'special_situations', etc.

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
    def actual_times_used(self):
        """
        Dynamically count actual ResearchProject records for this template's owner only.
        This is always accurate, even after projects are deleted.
        Filters by user_id for privacy/security.
        """
        return self.research_projects.filter_by(user_id=self.user_id).count()

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
    A research project is an active execution of a research template for COMPANY analysis.
    It tracks progress, time spent, findings, and ultimately investment decisions.

    Note: Sector research uses the free-form SectorAnalysis notebook, not this model.
    """
    __tablename__ = 'research_project'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'company_id', name='uq_research_project_user_company'),
        # Too-hard service filter_by(user_id=..., decision='pass')
        db.Index('idx_research_project_user_decision', 'user_id', 'decision'),
        # Priority service filter_by(user_id=..., status='active')
        db.Index('idx_research_project_user_status', 'user_id', 'status'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    template_id = db.Column(db.Integer, db.ForeignKey('research_template.id'), nullable=False, index=True)

    # Company being researched (required)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False, index=True)

    # Sector for analytics and Circle of Competence tracking
    sector_id = db.Column(db.Integer, db.ForeignKey('sector.id'), nullable=True, index=True)

    # If this project originated from an idea in the pipeline
    idea_id = db.Column(db.Integer, db.ForeignKey('idea_pipeline.id'), index=True)

    # Project metadata
    project_name = db.Column(db.String(200))
    investment_thesis = db.Column(db.Text)  # Evolving thesis as research progresses

    # Progress tracking
    current_step_index = db.Column(db.Integer, default=0)
    completed_steps = db.Column(db.JSON, default=list)  # Array of completed step indices
    step_notes = db.Column(db.JSON, default=dict)  # Notes for each step
    step_results = db.Column(db.JSON, default=dict)  # Detailed results for each step
    step_overrides = db.Column(db.JSON, default=dict)  # Override step configs (e.g., if checklist was deleted)
    workflow_snapshot = db.Column(db.JSON, nullable=True)  # Snapshot of template workflow_steps at project creation

    # Status tracking
    status = db.Column(db.String(50), default='active')  # RESEARCH_PROJECT_STATUSES
    kill_reason = db.Column(db.Text)  # Reason for killing the investment during screening

    # Time tracking - crucial for understanding where effort goes
    total_hours_spent = db.Column(db.Float, default=0.0)
    time_per_step = db.Column(db.JSON, default=dict)  # Track time for each step
    last_worked_at = db.Column(db.DateTime)

    # Decision tracking
    decision = db.Column(db.String(50))  # RESEARCH_DECISIONS
    decision_date = db.Column(db.DateTime)
    decision_confidence = db.Column(db.Integer)  # 1-10 scale
    decision_notes = db.Column(db.Text)

    # Watchlist tracking (can be set on active or completed projects)
    watch_reason = db.Column(db.String(50))  # WATCH_REASONS
    watch_notes = db.Column(db.Text)

    # Circle of Competence tracking (for Too Hard Basket analytics)
    within_circle_of_competence = db.Column(db.String(20))  # 'yes', 'no', 'unsure'

    # Too Hard / Mid-research pass tracking
    too_hard_reason = db.Column(db.String(100))  # 'too_complex', 'insufficient_info', 'outside_competence', 'better_opportunities', 'other'
    too_hard_notes = db.Column(db.Text)  # What they learned
    abandoned_at = db.Column(db.DateTime)  # When marked as too hard (kept for backwards compatibility)

    # If invested, track the outcome
    exit_date = db.Column(db.Date)

    # Key findings that influenced the decision
    key_findings = db.Column(db.JSON, default=list)
    # Red/green flags and must-exit criteria are journal entries on the
    # company (see app.services.findings); the properties below read them.

    # Companion session wrap-up summaries
    session_history = db.Column(db.JSON, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=now_utc)
    completed_at = db.Column(db.DateTime)

    # Relationships
    company = db.relationship('Company', backref='research_projects')
    sector = db.relationship('Sector', backref='research_projects')
    idea = db.relationship('IdeaPipeline', backref='research_project')
    work_sessions = db.relationship('WorkSession', backref='project',
                                   lazy='dynamic', cascade='all, delete-orphan')
    research_logs = db.relationship('ResearchLog', backref='project',
                                   lazy='dynamic', cascade='all, delete-orphan')

    # Loaded once per instance (and eager-loadable); expired on commit, and by
    # app.services.findings when it adds or deletes a finding.
    finding_journal_entries = db.relationship(
        'JournalEntry',
        primaryjoin="and_(foreign(JournalEntry.company_id) == ResearchProject.company_id, "
                    "foreign(JournalEntry.user_id) == ResearchProject.user_id, "
                    "JournalEntry.entry_type.in_(['red_flag', 'green_flag', 'must_exit']), "
                    "or_(JournalEntry.is_archived.is_(False), JournalEntry.is_archived.is_(None)))",
        order_by="[JournalEntry.created_at, JournalEntry.id]",
        viewonly=True,
    )

    def _finding_texts(self, finding_type):
        return [e.finding_line() for e in self.finding_journal_entries if e.entry_type == finding_type]

    @property
    def red_flags(self):
        return self._finding_texts('red_flag')

    @property
    def green_flags(self):
        return self._finding_texts('green_flag')

    @property
    def must_exit_criteria(self):
        return self._finding_texts('must_exit')

    @property
    def workflow_steps(self):
        """Return the project's workflow steps -- snapshot first, template fallback."""
        if self.workflow_snapshot:
            return self.workflow_snapshot
        if self.template and self.template.workflow_steps:
            return self.template.workflow_steps
        return []

    @property
    def step_count(self):
        """Number of steps in this project's workflow."""
        return len(self.workflow_steps)

    def get_step(self, step_index):
        """Safely get a specific step from the project's workflow."""
        steps = self.workflow_steps
        if steps and 0 <= step_index < len(steps):
            return steps[step_index]
        return None

    @property
    def progress_percentage(self):
        """
        Calculate the completion percentage of this project.

        This considers partial progress within steps (e.g., checklist items completed)
        to provide more granular progress tracking.
        """
        # Import here to avoid circular import
        from app.services.step_progress_calculator import StepProgressCalculator

        if not self.workflow_steps:
            return 0.0

        total_steps = self.step_count
        if total_steps == 0:
            return 0.0

        # Calculate progress for each step and average them
        total_progress = 0.0
        for step_index in range(total_steps):
            step_progress = StepProgressCalculator.get_step_progress(self, step_index)
            total_progress += step_progress

        # Average progress across all steps
        overall_progress = total_progress / total_steps
        return round(overall_progress, 1)

    @property
    def total_time_including_active(self):
        """
        Calculate total time spent including active sessions.

        Returns total hours including:
        - Completed sessions (stored in total_hours_spent)
        - Active sessions (end_time is NULL)
        """
        total = self.total_hours_spent or 0.0

        # Add time from active sessions
        active_sessions = self.work_sessions.filter(
            WorkSession.end_time.is_(None)
        ).all()

        for session in active_sessions:
            # Calculate duration from start_time to now
            start_time_aware = ensure_timezone_aware(session.start_time)
            current_time = now_utc()
            duration_seconds = (current_time - start_time_aware).total_seconds()
            duration_hours = duration_seconds / 3600
            total += duration_hours

        return round(total, 1)

    @property
    def current_step(self):
        """Get the current step details from the project's workflow snapshot"""
        return self.get_step(self.current_step_index)

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
    def investment_thesis_text(self):
        """Plain text version of investment_thesis for LLM prompts and embeddings"""
        return blocknote_to_text(self.investment_thesis) if self.investment_thesis else ''

    @property
    def subject_display_name(self):
        """Get display name for the company being researched"""
        if self.company:
            return self.company.name
        return "Unknown Company"

    def __repr__(self):
        return f'<ResearchProject {self.project_name or self.subject_display_name}>'


class WorkSession(db.Model):
    """
    A work session tracks individual research sessions within a project.
    This granular tracking helps investors understand their time allocation
    and identify which parts of their process are most time-consuming.
    """
    __tablename__ = 'work_session'
    __table_args__ = (
        # Time allocation filter(user_id=..., start_time >= ...)
        db.Index('idx_work_session_user_start', 'user_id', 'start_time'),
    )

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('research_project.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)

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

    # Quality markers
    confidence_level = db.Column(db.Integer)  # 1-10 scale for this session's work
    needs_followup = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<WorkSession {self.id} for Project {self.project_id}>'


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

    # Research Time Metrics
    total_research_hours = db.Column(db.Float, default=0)
    average_hours_per_company = db.Column(db.Float)
    most_time_consuming_step = db.Column(db.String(200))

    # Decision Quality Metrics
    total_investment_decisions = db.Column(db.Integer, default=0)
    invest_decisions = db.Column(db.Integer, default=0)
    pass_decisions = db.Column(db.Integer, default=0)
    average_confidence_score = db.Column(db.Float)

    # Behavioral Patterns
    most_productive_day = db.Column(db.String(20))  # Monday, Tuesday, etc.
    most_productive_hour = db.Column(db.Integer)  # 0-23
    research_streak_days = db.Column(db.Integer, default=0)
    last_research_date = db.Column(db.Date)

    # Timestamps
    last_updated = db.Column(db.DateTime, default=now_utc)

    def __repr__(self):
        return f'<ResearchMetrics for User {self.user_id}>'


class ResearchLog(db.Model):
    """
    Detailed log of all research activities for pattern analysis.
    This is the raw data that feeds into aggregated metrics.
    """
    __tablename__ = 'research_log'
    __table_args__ = (
        # Streak calculation filter(user_id=...) + timestamp
        db.Index('idx_research_log_user_timestamp', 'user_id', 'timestamp'),
    )

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


class FreeResearchQuestion(db.Model):
    """
    A custom research question created by the user.
    Can be linked to a research project step (project_id + step_index set)
    or standalone on a company (project_id is None).
    """
    __tablename__ = 'free_research_question'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)

    # Link to company (always present)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False, index=True)

    # Link to research project and step (nullable for standalone questions)
    project_id = db.Column(db.Integer, db.ForeignKey('research_project.id'), nullable=True, index=True)
    step_index = db.Column(db.Integer, nullable=True)  # Which step in the workflow (None for standalone)

    # Question content
    question_text = db.Column(db.Text, nullable=False)
    answer_content = db.Column(db.Text)  # BlockNote JSON content

    # Status tracking
    status = db.Column(db.String(20), default='exploring')  # 'exploring', 'answered'

    # Ordering
    order_index = db.Column(db.Integer, default=0)

    # Timestamps
    created_at = db.Column(db.DateTime, default=now_utc)
    updated_at = db.Column(db.DateTime, default=now_utc, onupdate=now_utc)
    answered_at = db.Column(db.DateTime)  # When marked as answered

    # Relationships
    user = db.relationship('User', backref=db.backref('free_research_questions', lazy='dynamic'))
    company = db.relationship('Company', backref=db.backref(
        'free_research_questions', lazy='dynamic', cascade='all, delete-orphan'
    ))
    project = db.relationship('ResearchProject', backref=db.backref(
        'free_research_questions', lazy='dynamic', cascade='all'
    ))

    def __repr__(self):
        return f'<FreeResearchQuestion {self.id}: {self.question_text[:50]}...>'


class ResearchSettings(db.Model):
    """
    Per-user tunable parameters for the research priority scoring algorithm.
    One row per user, created with defaults on first access (get-or-create).
    """
    __tablename__ = 'research_settings'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)

    # Focus limits
    active_project_limit = db.Column(db.Integer, default=3)
    pinned_project_id = db.Column(db.Integer, db.ForeignKey('research_project.id', ondelete='SET NULL'), nullable=True)

    # Scoring weights (must sum to 100)
    weight_momentum = db.Column(db.Integer, default=40)
    weight_proximity = db.Column(db.Integer, default=25)
    weight_staleness = db.Column(db.Integer, default=20)
    weight_signal = db.Column(db.Integer, default=15)

    # Tuning knobs
    momentum_half_life_days = db.Column(db.Integer, default=3)
    staleness_peak_days = db.Column(db.Integer, default=10)
    stale_warning_days = db.Column(db.Integer, default=14)
    stale_nudge_days = db.Column(db.Integer, default=21, server_default='21')
    stale_warning_min_progress = db.Column(db.Integer, default=30)

    # AI check: web searches allowed per run (Gather + loop-back, or the Quick call). 1–10.
    ai_check_search_budget = db.Column(db.Integer, nullable=False, default=5, server_default='5')

    def __repr__(self):
        return f'<ResearchSettings for User {self.user_id}>'

    @staticmethod
    def get_or_create(user_id):
        """Get existing settings or create with defaults."""
        settings = ResearchSettings.query.filter_by(user_id=user_id).first()
        if not settings:
            settings = ResearchSettings(user_id=user_id)
            db.session.add(settings)
            db.session.commit()
        elif settings.stale_nudge_days is None:
            settings.stale_nudge_days = 21
            db.session.commit()
        return settings


