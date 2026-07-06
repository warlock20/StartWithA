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

# app/models/journal.py

from app import db
from app.utils.time_utils import now_utc
from app.utils.blocknote_utils import blocknote_to_text


class DecisionJournal(db.Model):
    """
    Track investment decisions with pre-mortem and post-mortem analysis.
    This helps investors learn from both good and bad decisions.
    """
    __tablename__ = 'decision_journal'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey('research_project.id'), index=True)

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

    # Portfolio integration fields
    is_portfolio_decision = db.Column(db.Boolean, default=False, index=True)
    linked_research_id = db.Column(db.Integer, db.ForeignKey('research_project.id'), nullable=True)

    # Thesis quality tracking (for non-research purchases)
    thesis_depth = db.Column(db.String(50))  # 'comprehensive', 'brief', 'minimal'
    thesis_word_count = db.Column(db.Integer, default=0)  # Track thesis length
    non_research_source = db.Column(db.String(100))  # 'external_research', 'tip', 'gut_feeling', 'other'

    created_at = db.Column(db.DateTime, default=now_utc)
    updated_at = db.Column(db.DateTime, default=now_utc, onupdate=now_utc)

    # Relationships
    company = db.relationship('Company', backref='decision_journals')

    @property
    def investment_thesis_text(self):
        """Plain text version of investment_thesis for LLM prompts and embeddings"""
        return blocknote_to_text(self.investment_thesis) if self.investment_thesis else ''

    def __repr__(self):
        return f'<DecisionJournal {self.decision_type} for Company {self.company_id}>'


class JournalEntry(db.Model):
    """
    Enhanced journal entries that capture investment thinking over time.
    These are more structured than simple notes, designed to build knowledge.
    """
    __tablename__ = 'journal_entry'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)

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
    journal_entry_id = db.Column(db.Integer, db.ForeignKey('journal_entry.id'), nullable=False, index=True)

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
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False, index=True)

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

    @property
    def thesis_text(self):
        """Plain text version of thesis for LLM prompts and embeddings"""
        return blocknote_to_text(self.thesis) if self.thesis else ''

    def __repr__(self):
        return f'<ThesisEvolution v{self.version} for Company {self.company_id}>'


class LearningNote(db.Model):
    """
    Structured learning notes that capture investment lessons.
    These are meant to be reviewed and internalized over time.
    """
    __tablename__ = 'learning_note'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)

    # Learning content
    title = db.Column(db.String(200), nullable=False)
    lesson = db.Column(db.Text, nullable=False)

    # Categorization
    category = db.Column(db.String(100))  # 'mistake', 'success', 'process', 'market_wisdom', 'insight'
    subcategory = db.Column(db.String(100))  # More specific classification

    # Context
    context = db.Column(db.Text)  # The situation that led to this learning

    # Application
    how_to_apply = db.Column(db.Text)  # How to use this lesson in future

    # Examples
    examples = db.Column(db.JSON)  # Specific examples of this lesson
    anti_examples = db.Column(db.JSON)  # Counter-examples

    # Enhanced Source Attribution (for insights from legendary investors)
    source_type = db.Column(db.String(50))  # 'experience', 'book', 'mentor', 'article', 'podcast', 'video', 'letter', 'conference'
    source_detail = db.Column(db.String(200))  # Title or description
    source_url = db.Column(db.String(500))  # URL to source material
    source_author = db.Column(db.String(200))  # Investor/Author name (e.g., "Warren Buffett", "Howard Marks")
    source_date = db.Column(db.Date)  # Date of source material

    # Knowledge base metadata
    knowledge_type = db.Column(db.String(50))  # 'insight', 'lesson_learned', 'framework', 'mental_model', 'quote'
    topic_tags = db.Column(db.JSON)  # Specific topics: ['valuation', 'moat', 'management', 'psychology']
    investor_tags = db.Column(db.JSON)  # Investor names for filtering insights by source

    # Related entities
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'))
    company = db.relationship('Company', backref='learning_notes')
    decision_id = db.Column(db.Integer, db.ForeignKey('decision_journal.id'))

    # Review and reinforcement
    times_reviewed = db.Column(db.Integer, default=0)
    last_reviewed = db.Column(db.DateTime)
    importance = db.Column(db.Integer, default=5)  # 1-10 scale
    is_favorite = db.Column(db.Boolean, default=False)  # Star/favorite insights

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
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), index=True)  # Null for system templates

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
