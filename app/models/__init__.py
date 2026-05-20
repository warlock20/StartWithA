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
    CompanyResource,
    QualitativeAnalysis,
    FinancialData,
)
from .document_annotation import DocumentAnnotation
from .checklist import (
    Checklist,
    ChecklistItem,
    QuestionBankItem,
    DestinationCheckpoint,
    DocumentImport,
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
    ChecklistAnalysis,
    ChecklistAnswer,
    ResearchTemplate,
    ResearchProject,
    WorkSession,
    TemplateStep,
    ResearchMetrics,
    ResearchLog,
    FreeResearchQuestion,
    ResearchSettings,
)
from .sector import (
    Sector,
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
from .portfolio import (
    ExchangeRate,
    Transaction,
    PortfolioPosition,
    calculate_fifo_cost_basis,
    update_portfolio_position,
)
from .background_task import BackgroundTask
from .ai_intelligence import (
    ResearchOutcome,
    AIInsight,
    EmbeddingStore,
    MLPredictionLog,
)
from .configuration import (
    SystemConfig,
    InvestorProfile,
    UserInvestmentProfile,
)
from .prompt_management import (
    PromptVersion,
    PromptUsageLog,
)
from .ai_research_feedback import (
    AIResearchFeedback,
)
from .bias_check import (
    BiasCheckResult,
)
from .portfolio_insight import (
    PortfolioUIInsight,
)
from .market_sweep import (
    MarketSweep,
    MarketSweepCompany,
    MarketSweepDecision,
)



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
    'CompanyResource',
    'DocumentAnnotation',
    'QualitativeAnalysis',
    'FinancialData',
    # Checklist models
    'Checklist',
    'ChecklistItem',
    'QuestionBankItem',
    'DestinationCheckpoint',
    'DocumentImport',
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
    'ChecklistAnalysis',
    'ChecklistAnswer',
    'ResearchTemplate',
    'ResearchProject',
    'WorkSession',
    'TemplateStep',
    'ResearchMetrics',
    'ResearchLog',
    'FreeResearchQuestion',
    'ResearchSettings',
    # Sector models
    'Sector',
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
    # Portfolio models
    'ExchangeRate',
    'Transaction',
    'PortfolioPosition',
    'calculate_fifo_cost_basis',
    'update_portfolio_position',
    # Background task
    'BackgroundTask',
    # AI Intelligence models
    'ResearchOutcome',
    'AIInsight',
    'EmbeddingStore',
    'MLPredictionLog',
    # Configuration models
    'SystemConfig',
    'InvestorProfile',
    'UserInvestmentProfile',
    # Prompt Management models
    'PromptVersion',
    'PromptUsageLog',
    # AI Research Feedback models
    'AIResearchFeedback',
    # Bias Check models
    'BiasCheckResult',
    # Portfolio Insight models
    'PortfolioUIInsight',
    # Market Sweep models
    'MarketSweep',
    'MarketSweepCompany',
    'MarketSweepDecision',
]
