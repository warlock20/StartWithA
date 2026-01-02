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
# NOTE: Intelligence engine thresholds moved to database configuration
# ============================================================================
# These values are now stored in the database via SystemConfig table
# and managed through the investment profile settings UI.
#
# Defaults are automatically seeded by migration:
#   migrations/versions/8738fe6620b7_add_configuration_system.py
#
# Users can customize via: /settings/profile
# ============================================================================
