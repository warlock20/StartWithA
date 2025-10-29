# app/models/research.py

from app import db
from app.utils.time_utils import now_utc, ensure_timezone_aware


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
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

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

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey('research_template.id'), nullable=False)

    # Company being researched (required)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)

    # Sector for analytics and Circle of Competence tracking
    sector_id = db.Column(db.Integer, db.ForeignKey('sector.id'), nullable=True, index=True)

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
    step_overrides = db.Column(db.JSON, default=dict)  # Override step configs (e.g., if checklist was deleted)

    # Status tracking
    status = db.Column(db.String(50), default='active')  # 'active', 'completed', 'abandoned', 'killed'
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

    # Circle of Competence tracking (for Too Hard Basket analytics)
    within_circle_of_competence = db.Column(db.String(20))  # 'yes', 'no', 'unsure'

    # Too Hard / Abandon tracking
    too_hard_reason = db.Column(db.String(100))  # 'too_complex', 'insufficient_info', 'outside_competence', 'better_opportunities', 'other'
    too_hard_notes = db.Column(db.Text)  # What they learned
    abandoned_at = db.Column(db.DateTime)  # When marked as too hard

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
    sector = db.relationship('Sector', backref='research_projects')
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
