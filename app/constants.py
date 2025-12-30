"""
Application Constants
Centralized constants to avoid magic numbers throughout the codebase.
"""

# ============================================================================
# PAGINATION SETTINGS
# ============================================================================
TRANSACTIONS_PER_PAGE = 50
JOURNALS_PER_PAGE = 25
POSITIONS_PER_PAGE = 50
DEFAULT_PAGE_SIZE = 25

# ============================================================================
# ANALYTICS & INSIGHTS THRESHOLDS
# ============================================================================
MIN_TRADES_FOR_INSIGHTS = 3
"""Minimum number of completed trades needed to generate learning insights"""

MIN_OUTCOMES_FOR_CORRELATION = 3
"""Minimum research outcomes needed for correlation analysis"""

# ============================================================================
# CONFIDENCE SCORE RANGES
# ============================================================================
CONFIDENCE_LOW_MAX = 4
"""Maximum score for 'low' confidence (1-4)"""

CONFIDENCE_MEDIUM_MAX = 7
"""Maximum score for 'medium' confidence (5-7)"""

CONFIDENCE_HIGH_MIN = 8
"""Minimum score for 'high' confidence (8-10)"""

# ============================================================================
# HOLDING PERIOD BUCKETS (in days)
# ============================================================================
HOLD_PERIOD_SHORT_MAX = 30
"""Maximum days for 'short-term' holding (0-30 days)"""

HOLD_PERIOD_MEDIUM_SHORT_MAX = 90
"""Maximum days for 'medium-short' holding (31-90 days)"""

HOLD_PERIOD_MEDIUM_MAX = 180
"""Maximum days for 'medium' holding (91-180 days)"""

HOLD_PERIOD_MEDIUM_LONG_MAX = 365
"""Maximum days for 'medium-long' holding (181-365 days)"""

# Anything > 365 days is 'long-term'

# ============================================================================
# FORM FIELD LIMITS
# ============================================================================
MAX_DYNAMIC_FORM_FIELDS = 50
"""Maximum number of dynamic form fields (bull/bear cases, etc.)"""

MIN_THESIS_WORD_COUNT = 20
"""Minimum word count for investment thesis"""

THESIS_BRIEF_WORD_COUNT = 50
"""Word count threshold for 'brief' thesis classification"""

THESIS_COMPREHENSIVE_WORD_COUNT = 100
"""Word count threshold for 'comprehensive' thesis classification"""

# ============================================================================
# PERFORMANCE GRADING
# ============================================================================
GRADE_A_THRESHOLD = 90
"""Minimum score for 'A' grade"""

GRADE_B_THRESHOLD = 80
"""Minimum score for 'B' grade"""

GRADE_C_THRESHOLD = 70
"""Minimum score for 'C' grade"""

GRADE_D_THRESHOLD = 60
"""Minimum score for 'D' grade"""

# Anything < 60 is 'F'

# ============================================================================
# TOP/BOTTOM PERFORMERS
# ============================================================================
DEFAULT_TOP_PERFORMERS_LIMIT = 5
"""Default number of top performers to show"""

DEFAULT_BOTTOM_PERFORMERS_LIMIT = 5
"""Default number of bottom performers to show"""

# ============================================================================
# RECENT ITEMS LIMITS
# ============================================================================
RECENT_TRANSACTIONS_LIMIT = 10
"""Number of recent transactions to show on dashboard"""

RECENT_DECISIONS_LIMIT = 10
"""Number of recent decisions to show"""

UPCOMING_CHECKPOINTS_LIMIT = 5
"""Number of upcoming checkpoints to show on dashboard"""

# ============================================================================
# TIMEFRAME DEFAULTS
# ============================================================================
DEFAULT_CHECKPOINT_LOOKBACK_DAYS = 30
"""Default number of days to look back/ahead for checkpoints"""

MONTHLY_PERFORMANCE_MONTHS = 12
"""Number of months to show in monthly performance chart"""

# ============================================================================
# VALIDATION LIMITS
# ============================================================================
MAX_FILE_UPLOAD_SIZE_MB = 10
"""Maximum file upload size in megabytes"""

MAX_COMPANY_NAME_LENGTH = 255
"""Maximum length for company name"""

MAX_TICKER_LENGTH = 10
"""Maximum length for ticker symbol"""

# ============================================================================
# CURRENCY PRECISION
# ============================================================================
CURRENCY_DECIMAL_PLACES = 2
"""Number of decimal places for currency values"""

PERCENTAGE_DECIMAL_PLACES = 1
"""Number of decimal places for percentage values"""

# ============================================================================
# CACHE TTL (Time To Live)
# ============================================================================
PRICE_CACHE_TTL_MINUTES = 15
"""How long to cache stock prices before refreshing"""

# ============================================================================
# INTELLIGENT ENGINE DEFAULTS
# (These can be overridden per user in UserIntelligenceProfile)
# ============================================================================
DEFAULT_POSITION_CONCENTRATION_THRESHOLD = 25.0
"""Default threshold for single position concentration warning (%)"""

DEFAULT_SECTOR_CONCENTRATION_THRESHOLD = 40.0
"""Default threshold for sector concentration warning (%)"""

DEFAULT_CORRELATION_THRESHOLD = 70.0
"""Default threshold for high correlation warning (%)"""

DEFAULT_RUNUP_LOOKBACK_DAYS = 90
"""Default lookback period for run-up detection (days)"""

DEFAULT_RUNUP_THRESHOLD_PCT = 30.0
"""Default threshold for run-up warning (%)"""

DEFAULT_CHASING_RETURNS_CAGR_THRESHOLD = 50.0
"""Default CAGR threshold for 'chasing returns' warning (%)"""

DEFAULT_CHASING_RETURNS_MIN_DAYS = 90
"""Minimum holding period before checking CAGR for chasing returns"""



# ============================================================================
# BEHAVIORAL PATTERN DETECTION
# (Part of Intelligence Engine)
# ============================================================================

# --- Disposition Effect: Selling Winners ---
DEFAULT_WINNER_THRESHOLD_PCT = 15.0
"""Position is considered a 'winner' if up 15%+"""

DEFAULT_WINNER_MIN_HOLD_DAYS = 30
"""Minimum days to hold before 'selling too early' warning applies"""

DEFAULT_WINNER_EARLY_SELL_DAYS = 90
"""Selling a winner before this many days triggers warning"""

# --- Disposition Effect: Holding Losers ---
DEFAULT_LOSER_THRESHOLD_PCT = -15.0
"""Position is considered a 'loser' if down 15%+"""

DEFAULT_LOSER_HOLD_DAYS_WARNING = 180
"""Days holding a loser before warning about holding too long"""

DEFAULT_LOSER_SEVERE_DAYS = 365
"""Days holding a loser before high-severity warning"""

DEFAULT_LOSER_SEVERE_PCT = -30.0
"""Loss % considered severe (for high-severity warning)"""

# --- Averaging Down ---
DEFAULT_AVERAGING_DOWN_COUNT = 2
"""Number of previous buys into losing position before warning"""

DEFAULT_AVERAGING_DOWN_SEVERE_COUNT = 4
"""Number of buys for high-severity warning"""

# --- Overconfidence Detection ---
DEFAULT_OVERCONFIDENCE_MIN_TRADES = 5
"""Minimum completed trades needed for overconfidence analysis"""

DEFAULT_OVERCONFIDENCE_HIGH_CONFIDENCE = 8
"""Confidence score considered 'high' (8-10 scale)"""

DEFAULT_OVERCONFIDENCE_POOR_OUTCOME_PCT = -10.0
"""Return % considered a poor outcome for overconfidence analysis"""

DEFAULT_OVERCONFIDENCE_POOR_RATE_THRESHOLD = 0.40
"""% of high-confidence trades with poor outcomes to trigger warning"""
