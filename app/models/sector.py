# app/models/sector.py

from app import db
from app.utils.time_utils import now_utc
import re


class Sector(db.Model):
    """
    Master sector registry for the entire platform.
    Provides standardized sector definitions, metadata, and analytics.
    Links all sector-related data across the platform (companies, research, ideas, etc.)
    """
    __tablename__ = 'sector'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)

    # Core identification (multiple variants for flexibility)
    name = db.Column(db.String(100), nullable=False)
    # Primary name: "Financial Technology", "Software as a Service", etc.

    display_name = db.Column(db.String(100), nullable=False)
    # How to display: "FinTech", "SaaS", "Healthcare IT"

    slug = db.Column(db.String(100), nullable=False, index=True)
    # URL-friendly: "fintech", "saas", "healthcare-it"

    # Alternative names for matching and search
    aliases = db.Column(db.JSON, nullable=True)
    # List: ["FinTech", "Financial Tech", "Financial Technology", "Banking Tech"]

    # Categorization and hierarchy
    parent_sector_id = db.Column(db.Integer, db.ForeignKey('sector.id'), nullable=True)
    # For hierarchical sectors: "Cloud Computing" parent of "SaaS"

    category = db.Column(db.String(50), nullable=True)
    # High-level: 'technology', 'healthcare', 'finance', 'consumer', 'industrial'

    # Rich metadata
    description = db.Column(db.Text, nullable=True)
    # What defines this sector

    key_characteristics = db.Column(db.JSON, nullable=True)
    # List of defining traits: ["Recurring revenue", "Network effects", "High margins"]

    typical_metrics = db.Column(db.JSON, nullable=True)
    # What to look for: {"key_ratios": ["ARR growth", "NRR", "CAC/LTV"], ...}

    # Visual customization
    color = db.Column(db.String(20), nullable=True)
    # Visual theming: "#3498db"

    icon = db.Column(db.String(50), nullable=True)
    # Icon class or emoji: "💰", "bi-bank"

    # Status and type
    status = db.Column(db.String(20), default='active')
    # 'active', 'archived', 'merged'

    is_default = db.Column(db.Boolean, default=False)
    # System-provided vs user-created

    merged_into_id = db.Column(db.Integer, db.ForeignKey('sector.id'), nullable=True)
    # If user merges two sectors, track the target

    # Cached analytics (updated periodically via update_analytics())
    total_companies = db.Column(db.Integer, default=0)
    companies_analyzed = db.Column(db.Integer, default=0)
    companies_invested = db.Column(db.Integer, default=0)
    total_research_hours = db.Column(db.Float, default=0)

    # Circle of Competence tracking (cached)
    coc_yes_count = db.Column(db.Integer, default=0)
    coc_no_count = db.Column(db.Integer, default=0)
    coc_unsure_count = db.Column(db.Integer, default=0)

    # Timestamps
    created_at = db.Column(db.DateTime, default=now_utc, nullable=False)
    updated_at = db.Column(db.DateTime, default=now_utc, onupdate=now_utc, nullable=False)
    last_researched = db.Column(db.DateTime, nullable=True)

    # Relationships
    user = db.relationship('User', backref='sectors')

    parent_sector = db.relationship(
        'Sector',
        remote_side=[id],
        backref='sub_sectors',
        foreign_keys=[parent_sector_id]
    )

    merged_into = db.relationship(
        'Sector',
        remote_side=[id],
        foreign_keys=[merged_into_id]
    )

    # Ensure unique sector slugs per user
    __table_args__ = (
        db.UniqueConstraint('user_id', 'slug', name='_user_sector_slug_uc'),
    )

    @staticmethod
    def make_slug(name):
        """Create URL-friendly slug from sector name"""
        import unicodedata
        # Remove accents and convert to ASCII
        name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
        # Convert to lowercase and replace spaces/special chars with hyphens
        slug = re.sub(r'[^\w\s-]', '', name.lower())
        slug = re.sub(r'[-\s]+', '-', slug).strip('-')
        return slug

    @property
    def full_name(self):
        """Get full hierarchical name"""
        if self.parent_sector:
            return f"{self.parent_sector.display_name} > {self.display_name}"
        return self.display_name

    @property
    def success_rate(self):
        """Calculate investment success rate"""
        total = self.companies_analyzed + self.companies_invested
        if total == 0:
            return 0
        return round((self.companies_invested / total) * 100, 1)

    @property
    def coc_confidence(self):
        """Calculate Circle of Competence confidence percentage"""
        total = self.coc_yes_count + self.coc_no_count + self.coc_unsure_count
        if total == 0:
            return 0
        return round((self.coc_yes_count / total) * 100, 1)

    @property
    def competence_level(self):
        """Get competence level: expert, proficient, developing, novice"""
        if self.companies_analyzed < 2:
            return {'level': 'novice', 'emoji': '🔴', 'label': 'Novice'}

        confidence = self.coc_confidence
        success = self.success_rate

        if confidence >= 70 and success >= 30:
            return {'level': 'expert', 'emoji': '🟢', 'label': 'Expert'}
        elif confidence >= 50 and success >= 20:
            return {'level': 'proficient', 'emoji': '🟡', 'label': 'Proficient'}
        elif confidence >= 30:
            return {'level': 'developing', 'emoji': '🟠', 'label': 'Developing'}
        else:
            return {'level': 'novice', 'emoji': '🔴', 'label': 'Novice'}

    def matches_name(self, search_term):
        """Check if search term matches this sector (for autocomplete)"""
        search_lower = search_term.lower().strip()

        # Check main name
        if search_lower in self.name.lower():
            return True

        # Check display name
        if search_lower in self.display_name.lower():
            return True

        # Check slug
        if search_lower == self.slug:
            return True

        # Check aliases
        if self.aliases:
            return any(search_lower in alias.lower() for alias in self.aliases)

        return False

    def update_analytics(self):
        """Recalculate cached analytics from related records"""
        from app.models.company import Company
        from app.models.research import ResearchProject
        from app.models.idea_pipeline import IdeaPipeline

        # Count companies
        self.total_companies = Company.query.filter_by(
            user_id=self.user_id,
            sector_id=self.id
        ).count()

        # Count research projects
        projects = ResearchProject.query.filter_by(
            user_id=self.user_id,
            sector_id=self.id
        ).all()

        self.companies_analyzed = len([p for p in projects if p.status in ['completed', 'abandoned']])
        self.companies_invested = len([p for p in projects if p.decision == 'invest'])
        self.total_research_hours = sum(p.total_hours_spent or 0 for p in projects)

        # Count CoC responses
        self.coc_yes_count = len([p for p in projects if p.within_circle_of_competence == 'yes'])
        self.coc_no_count = len([p for p in projects if p.within_circle_of_competence == 'no'])
        self.coc_unsure_count = len([p for p in projects if p.within_circle_of_competence == 'unsure'])

        # Update last researched
        if projects:
            latest = max(projects, key=lambda p: p.last_worked_at or p.created_at)
            self.last_researched = latest.last_worked_at or latest.created_at

    def __repr__(self):
        return f'<Sector "{self.display_name}" ({self.slug})>'


class SectorAnalysis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    # Link to the Sector being analyzed
    sector_id = db.Column(db.Integer, db.ForeignKey("sector.id"), nullable=False, index=True)

    # Document View content (generated from canvas or manually written)
    document_content = db.Column(db.Text, nullable=True)

    # Key takeaways from the research
    key_takeaways = db.Column(db.Text, nullable=True)

    # Research status and tracking
    status = db.Column(db.String(20), nullable=False, default='active')  # active, archived
    total_time_spent = db.Column(db.Integer, nullable=False, default=0)  # in seconds
    archived_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=now_utc)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=now_utc, onupdate=now_utc
    )

    # Relationships
    sector = db.relationship('Sector', backref='analyses')

    sections = db.relationship('SectorResearchSection', backref='sector_analysis',
                              lazy='dynamic', cascade='all, delete-orphan',
                              order_by='SectorResearchSection.display_order')

    # Ensure a user can only have one analysis notebook per sector
    __table_args__ = (
        db.UniqueConstraint("user_id", "sector_id", name="uq_user_sector_id"),
    )

    @property
    def word_count(self):
        """Calculate total word count from document content and atomic notes"""
        total_words = 0

        # Count words from document content
        if self.document_content:
            text = re.sub(r'<[^>]+>', '', self.document_content)
            total_words += len(text.split())

        # Count words from all atomic notes (using canvas_notes relationship)
        for note in self.canvas_notes.all():
            if note.content:
                text = re.sub(r'<[^>]+>', '', note.content)
                total_words += len(text.split())

        return total_words

    @property
    def companies_count(self):
        """Count companies in this sector"""
        from .company import Company
        return Company.query.filter_by(
            user_id=self.user_id,
            sector_id=self.sector_id
        ).count()

    @property
    def researched_companies_count(self):
        """Count companies with completed research projects"""
        from .company import Company
        from .research import ResearchProject
        companies = Company.query.filter_by(
            user_id=self.user_id,
            sector_id=self.sector_id
        ).all()

        researched = 0
        for company in companies:
            has_research = ResearchProject.query.filter_by(
                user_id=self.user_id,
                company_id=company.id,
                status='completed'
            ).first()
            if has_research:
                researched += 1
        return researched

    @property
    def sources_count(self):
        """Count research sources added"""
        return self.sources.count()

    @property
    def questions_count(self):
        """Count questions in question bank for this sector"""
        from .checklist import QuestionBankItem
        return QuestionBankItem.query.filter_by(
            user_id=self.user_id,
            sector_id=self.sector_id
        ).count()

    @property
    def sector_name(self):
        """Backward compatibility property - returns sector display name"""
        return self.sector.display_name if self.sector else "Unknown Sector"

    @property
    def research_progress_score(self):
        """
        Calculate comprehensive research progress score (0-100)
        Weighted: word_count 30%, time 20%, companies 25%, sources 15%, questions 10%
        """
        # Word count score (0-100)
        word_count = self.word_count
        if word_count >= 5000:
            word_score = 100
        elif word_count >= 3000:
            word_score = 80
        elif word_count >= 1500:
            word_score = 60
        elif word_count >= 500:
            word_score = 40
        else:
            word_score = min((word_count / 500) * 40, 40)

        # Time spent score (0-100)
        hours = self.total_time_spent / 3600
        if hours >= 10:
            time_score = 100
        elif hours >= 6:
            time_score = 80
        elif hours >= 3:
            time_score = 60
        elif hours >= 1:
            time_score = 40
        else:
            time_score = min((hours / 1) * 40, 40)

        # Companies analyzed score (0-100)
        researched = self.researched_companies_count
        if researched >= 15:
            companies_score = 100
        elif researched >= 10:
            companies_score = 80
        elif researched >= 5:
            companies_score = 60
        elif researched >= 2:
            companies_score = 40
        else:
            companies_score = min((researched / 2) * 40, 40)

        # Sources score (0-100)
        sources = self.sources_count
        if sources >= 15:
            sources_score = 100
        elif sources >= 10:
            sources_score = 80
        elif sources >= 5:
            sources_score = 60
        elif sources >= 2:
            sources_score = 40
        else:
            sources_score = min((sources / 2) * 40, 40)

        # Questions score (0-100)
        questions = self.questions_count
        if questions >= 25:
            questions_score = 100
        elif questions >= 15:
            questions_score = 80
        elif questions >= 8:
            questions_score = 60
        elif questions >= 3:
            questions_score = 40
        else:
            questions_score = min((questions / 3) * 40, 40)

        # Weighted average
        total_score = (
            word_score * 0.30 +
            time_score * 0.20 +
            companies_score * 0.25 +
            sources_score * 0.15 +
            questions_score * 0.10
        )

        return int(total_score)

    @property
    def progress_breakdown(self):
        """
        Get detailed breakdown of progress metrics with targets.
        Returns dict with individual scores, current values, targets, and recommendations.
        """
        word_count = self.word_count
        hours = self.total_time_spent / 3600
        researched = self.researched_companies_count
        sources = self.sources_count
        questions = self.questions_count

        # Calculate individual scores (same logic as research_progress_score)
        if word_count >= 5000:
            word_score = 100
        elif word_count >= 3000:
            word_score = 80
        elif word_count >= 1500:
            word_score = 60
        elif word_count >= 500:
            word_score = 40
        else:
            word_score = min((word_count / 500) * 40, 40)

        if hours >= 10:
            time_score = 100
        elif hours >= 6:
            time_score = 80
        elif hours >= 3:
            time_score = 60
        elif hours >= 1:
            time_score = 40
        else:
            time_score = min((hours / 1) * 40, 40)

        if researched >= 15:
            companies_score = 100
        elif researched >= 10:
            companies_score = 80
        elif researched >= 5:
            companies_score = 60
        elif researched >= 2:
            companies_score = 40
        else:
            companies_score = min((researched / 2) * 40, 40)

        if sources >= 15:
            sources_score = 100
        elif sources >= 10:
            sources_score = 80
        elif sources >= 5:
            sources_score = 60
        elif sources >= 2:
            sources_score = 40
        else:
            sources_score = min((sources / 2) * 40, 40)

        if questions >= 25:
            questions_score = 100
        elif questions >= 15:
            questions_score = 80
        elif questions >= 8:
            questions_score = 60
        elif questions >= 3:
            questions_score = 40
        else:
            questions_score = min((questions / 3) * 40, 40)

        # Determine next targets for each metric
        def get_next_target(current, thresholds):
            """Get next target value and score from thresholds"""
            for threshold, score_val in thresholds:
                if current < threshold:
                    return threshold, score_val
            return None, 100

        word_targets = [(500, 40), (1500, 60), (3000, 80), (5000, 100)]
        time_targets = [(1, 40), (3, 60), (6, 80), (10, 100)]
        company_targets = [(2, 40), (5, 60), (10, 80), (15, 100)]
        source_targets = [(2, 40), (5, 60), (10, 80), (15, 100)]
        question_targets = [(3, 40), (8, 60), (15, 80), (25, 100)]

        word_next, word_target_score = get_next_target(word_count, word_targets)
        time_next, time_target_score = get_next_target(hours, time_targets)
        company_next, company_target_score = get_next_target(researched, company_targets)
        source_next, source_target_score = get_next_target(sources, source_targets)
        question_next, question_target_score = get_next_target(questions, question_targets)

        return {
            'word_count': {
                'current': word_count,
                'score': int(word_score),
                'weight': 30,
                'next_target': word_next,
                'target_score': word_target_score,
                'label': 'Word Count',
                'icon': '📝'
            },
            'time_spent': {
                'current': hours,
                'current_formatted': self.time_spent_formatted,
                'score': int(time_score),
                'weight': 20,
                'next_target': time_next,
                'target_score': time_target_score,
                'label': 'Time Spent',
                'icon': '⏱️'
            },
            'companies': {
                'current': researched,
                'score': int(companies_score),
                'weight': 25,
                'next_target': company_next,
                'target_score': company_target_score,
                'label': 'Companies Researched',
                'icon': '🏢'
            },
            'sources': {
                'current': sources,
                'score': int(sources_score),
                'weight': 15,
                'next_target': source_next,
                'target_score': source_target_score,
                'label': 'Research Sources',
                'icon': '🔗'
            },
            'questions': {
                'current': questions,
                'score': int(questions_score),
                'weight': 10,
                'next_target': question_next,
                'target_score': question_target_score,
                'label': 'Questions Bank',
                'icon': '❓'
            }
        }

    @property
    def progress_stage(self):
        """Get progress stage emoji and label"""
        score = self.research_progress_score
        if score >= 76:
            return {'emoji': '🟢', 'label': 'Comprehensive'}
        elif score >= 51:
            return {'emoji': '🟠', 'label': 'Advanced'}
        elif score >= 26:
            return {'emoji': '🟡', 'label': 'In Progress'}
        else:
            return {'emoji': '🔴', 'label': 'Early Stage'}

    @property
    def time_spent_formatted(self):
        """Format total time spent as readable string"""
        hours = self.total_time_spent // 3600
        minutes = (self.total_time_spent % 3600) // 60
        if hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"

    @property
    def completion_percentage(self):
        """Calculate research completion based on sections with content"""
        total_sections = self.sections.count()
        if total_sections == 0:
            return 0
        completed_sections = self.sections.filter(
            db.and_(
                SectorResearchSection.content.isnot(None),
                SectorResearchSection.content != ''
            )
        ).count()
        return int((completed_sections / total_sections) * 100)

    @property
    def last_edited_section(self):
        """Get the most recently edited section"""
        return self.sections.order_by(SectorResearchSection.updated_at.desc()).first()

    def __repr__(self):
        sector_name = self.sector.display_name if self.sector else 'Unknown'
        return f'<SectorAnalysis for "{sector_name}" by User {self.user_id}>'


class SectorResearchSection(db.Model):
    """
    Flexible research sections for sector analysis.
    Users can customize, reorder, add, or remove sections in the future.
    """
    __tablename__ = 'sector_research_section'

    id = db.Column(db.Integer, primary_key=True)
    sector_analysis_id = db.Column(db.Integer, db.ForeignKey('sector_analysis.id'), nullable=False)

    # Section metadata
    title = db.Column(db.String(200), nullable=False)
    icon = db.Column(db.String(50), nullable=True)  # Emoji or icon class
    description = db.Column(db.String(500), nullable=True)  # Helpful description/prompt

    # Rich text content (HTML from Quill.js)
    content = db.Column(db.Text, nullable=True)

    # Display order (for future drag-and-drop reordering)
    display_order = db.Column(db.Integer, nullable=False, default=0)

    # Section type for future categorization
    section_type = db.Column(db.String(50), nullable=True, default='custom')
    # Types: 'overview', 'analysis', 'trends', 'risks', 'opportunities', 'custom'

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=now_utc)
    updated_at = db.Column(db.DateTime, nullable=False, default=now_utc, onupdate=now_utc)

    # Metadata for future features
    is_visible = db.Column(db.Boolean, default=True)  # Users can hide sections
    is_locked = db.Column(db.Boolean, default=False)  # Prevent deletion of important sections

    @property
    def is_completed(self):
        """Check if section has content"""
        return self.content is not None and len(self.content.strip()) > 0

    @property
    def word_count(self):
        """Estimate word count (strip HTML tags for rough count)"""
        if not self.content:
            return 0
        import re
        text = re.sub(r'<[^>]+>', '', self.content)
        return len(text.split())

    def __repr__(self):
        return f'<SectorResearchSection "{self.title}" for Analysis {self.sector_analysis_id}>'


class SectorResearchSource(db.Model):
    """
    Track research sources and references for sector analysis.
    Helps organize articles, reports, videos, and other materials.
    """
    __tablename__ = 'sector_research_source'

    id = db.Column(db.Integer, primary_key=True)
    sector_analysis_id = db.Column(db.Integer, db.ForeignKey('sector_analysis.id'), nullable=False)

    # Source metadata
    title = db.Column(db.String(300), nullable=False)
    url = db.Column(db.String(1000), nullable=True)
    source_type = db.Column(db.String(50), nullable=False, default='article')
    # Types: 'article', 'report', 'video', 'podcast', 'book', 'other'

    # Description and notes
    description = db.Column(db.Text, nullable=True)
    key_takeaways = db.Column(db.Text, nullable=True)

    # Publication info
    author = db.Column(db.String(200), nullable=True)
    publisher = db.Column(db.String(200), nullable=True)
    published_date = db.Column(db.Date, nullable=True)

    # Categorization
    tags = db.Column(db.String(500), nullable=True)  # Comma-separated tags
    relevance_score = db.Column(db.Integer, nullable=True)  # 1-5 rating

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=now_utc)
    accessed_at = db.Column(db.DateTime, nullable=True)  # Last time user accessed

    # Relationship back to sector analysis
    sector_analysis = db.relationship('SectorAnalysis', backref=db.backref('sources', lazy='dynamic', cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<SectorResearchSource "{self.title}" for Analysis {self.sector_analysis_id}>'


class SectorResearchSnippet(db.Model):
    """
    Save and categorize key research snippets/passages for quick reference.
    Helps organize important findings by category (competitive advantage, risks, etc.)
    """
    __tablename__ = 'sector_research_snippet'

    id = db.Column(db.Integer, primary_key=True)
    sector_analysis_id = db.Column(db.Integer, db.ForeignKey('sector_analysis.id'), nullable=False)

    # Snippet content
    content = db.Column(db.Text, nullable=False)

    # Categorization
    category = db.Column(db.String(50), nullable=False)
    # Categories: 'competitive_advantage', 'risks', 'valuation', 'growth_drivers',
    #             'industry_trends', 'management', 'other'

    # Optional metadata
    tags = db.Column(db.String(500), nullable=True)  # Comma-separated custom tags
    notes = db.Column(db.Text, nullable=True)  # Additional context/notes
    source_reference = db.Column(db.String(300), nullable=True)  # Where this came from

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=now_utc)
    updated_at = db.Column(db.DateTime, nullable=True, onupdate=now_utc)

    # Relationships
    sector_analysis = db.relationship('SectorAnalysis', backref=db.backref('snippets', lazy='dynamic', cascade='all, delete-orphan'))

    # Many-to-many relationship with companies
    linked_companies = db.relationship(
        'Company',
        secondary='sector_snippet_companies',
        lazy='dynamic',
        backref=db.backref('sector_snippets', lazy='dynamic')
    )

    def __repr__(self):
        return f'<SectorResearchSnippet {self.category} for Analysis {self.sector_analysis_id}>'


class SectorSection(db.Model):
    """
    Sections for organizing atomic notes in the research canvas.
    Examples: "Key Themes", "Risks & Challenges", "Growth Drivers"
    """
    __tablename__ = 'sector_section'

    id = db.Column(db.Integer, primary_key=True)
    sector_analysis_id = db.Column(db.Integer, db.ForeignKey('sector_analysis.id'), nullable=False)

    # Section metadata
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)

    # Ordering
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    # Visual styling (optional)
    icon = db.Column(db.String(50), nullable=True)  # Bootstrap icon class
    color = db.Column(db.String(20), nullable=True)  # Color theme

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=now_utc)
    updated_at = db.Column(db.DateTime, nullable=True, onupdate=now_utc)

    # Relationships
    sector_analysis = db.relationship('SectorAnalysis', backref=db.backref('canvas_sections', lazy='dynamic', cascade='all, delete-orphan', order_by='SectorSection.sort_order'))

    def __repr__(self):
        return f'<SectorSection "{self.title}" for Analysis {self.sector_analysis_id}>'


class SectorNote(db.Model):
    """
    Atomic note cards for the research canvas.
    Each note is a self-contained piece of information that can be organized into sections.
    """
    __tablename__ = 'sector_note'

    id = db.Column(db.Integer, primary_key=True)
    sector_analysis_id = db.Column(db.Integer, db.ForeignKey('sector_analysis.id'), nullable=False)
    section_id = db.Column(db.Integer, db.ForeignKey('sector_section.id'), nullable=True)  # Null = unorganized/inbox

    # Note content
    title = db.Column(db.String(300), nullable=False)
    content = db.Column(db.Text, nullable=False)

    # Metadata
    note_type = db.Column(db.String(50), nullable=False, default='note')
    # Types: 'note' (user created), 'ai_insight' (from Gemini), 'web_clip' (from browser), 'snippet' (saved from editor)

    source_reference = db.Column(db.String(500), nullable=True)  # URL or reference
    source_title = db.Column(db.String(300), nullable=True)  # Title of source

    # Tagging and categorization
    tags = db.Column(db.String(500), nullable=True)  # Comma-separated tags

    # Positioning within section
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=now_utc)
    updated_at = db.Column(db.DateTime, nullable=True, onupdate=now_utc)

    # Relationships
    sector_analysis = db.relationship('SectorAnalysis', backref=db.backref('canvas_notes', lazy='dynamic', cascade='all, delete-orphan'))
    section = db.relationship('SectorSection', backref=db.backref('section_notes', lazy='dynamic', cascade='all, delete-orphan', order_by='SectorNote.sort_order'))

    # Many-to-many relationship with companies
    linked_companies = db.relationship(
        'Company',
        secondary='sector_note_companies',
        lazy='dynamic',
        backref=db.backref('sector_notes', lazy='dynamic')
    )

    def __repr__(self):
        return f'<SectorNote "{self.title}" in Section {self.section_id}>'
