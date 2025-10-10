# app/models/__init__.py
# This module imports and exposes all models for backward compatibility

from app import db, login_manager

# Import association tables FIRST (they're referenced by models)
from .associations import (
    favorite_companies,
    competitors_association,
    sector_note_companies,
    sector_snippet_companies,
)

# Import models in dependency order
from .user import User
from .company import (
    Company,
    CompanyDocument,
    CompanyArticle,
    ScuttlebuttAnalysis,
    QualitativeAnalysis,
    FinancialData,
)
from .checklist import (
    Checklist,
    ChecklistItem,
    QuestionBankItem,
    DestinationCheckpoint,
    DocumentImport,
    OnboardingProgress,
)
from .idea_pipeline import (
    IdeaPipeline,
    KillChecklist,
    KillCriterion,
    KillSession,
    KillAnswer,
    KillChecklistSuggestion,
    IdeaSourceAnalysis,
    MistakeLog,
)
from .research import (
    ResearchSession,
    ResearchAnswer,
    ResearchTemplate,
    ResearchProject,
    WorkSession,
    TemplateStep,
    ResearchMetrics,
    ResearchLog,
)
from .sector import (
    SectorAnalysis,
    SectorResearchSection,
    SectorResearchSource,
    SectorResearchSnippet,
    SectorSection,
    SectorNote,
)
from .journal import (
    DecisionJournal,
    JournalEntry,
    JournalAttachment,
    ThesisEvolution,
    LearningNote,
    JournalTemplate,
    WeeklyReview,
    InvestmentPostMortem,
    LearningPath,
    PatternRecognition,
)
from .background_task import BackgroundTask


# User loader function required by Flask-Login
# This function is called to reload the user object from the user ID stored in the session
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Export all models for backward compatibility
__all__ = [
    # Database instance
    'db',
    # Association tables
    'favorite_companies',
    'competitors_association',
    'sector_note_companies',
    'sector_snippet_companies',
    # User
    'User',
    # Company models
    'Company',
    'CompanyDocument',
    'CompanyArticle',
    'ScuttlebuttAnalysis',
    'QualitativeAnalysis',
    'FinancialData',
    # Checklist models
    'Checklist',
    'ChecklistItem',
    'QuestionBankItem',
    'DestinationCheckpoint',
    'DocumentImport',
    'OnboardingProgress',
    # Idea Pipeline models
    'IdeaPipeline',
    'KillChecklist',
    'KillCriterion',
    'KillSession',
    'KillAnswer',
    'KillChecklistSuggestion',
    'IdeaSourceAnalysis',
    'MistakeLog',
    # Research models
    'ResearchSession',
    'ResearchAnswer',
    'ResearchTemplate',
    'ResearchProject',
    'WorkSession',
    'TemplateStep',
    'ResearchMetrics',
    'ResearchLog',
    # Sector models
    'SectorAnalysis',
    'SectorResearchSection',
    'SectorResearchSource',
    'SectorResearchSnippet',
    'SectorSection',
    'SectorNote',
    # Journal models
    'DecisionJournal',
    'JournalEntry',
    'JournalAttachment',
    'ThesisEvolution',
    'LearningNote',
    'JournalTemplate',
    'WeeklyReview',
    'InvestmentPostMortem',
    'LearningPath',
    'PatternRecognition',
    # Background task
    'BackgroundTask',
]
