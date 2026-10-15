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

"""
Application Constants
Centralized constants to avoid magic numbers throughout the codebase.
"""

# ============================================================================
# PAGINATION SETTINGS
# ============================================================================
JOURNALS_PER_PAGE = 25

# ============================================================================
# ANALYTICS & INSIGHTS THRESHOLDS
# ============================================================================
MIN_TRADES_FOR_INSIGHTS = 3
"""Minimum number of completed trades needed to generate learning insights"""

# ============================================================================
# FORM FIELD LIMITS
# ============================================================================
MAX_DYNAMIC_FORM_FIELDS = 50
"""Maximum number of dynamic form fields (bull/bear cases, etc.)"""

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

CHECKPOINT_ANALYSIS_WINDOW_DAYS = 30
"""Days ahead to include checkpoints for AI analysis (overdue + this window)"""

CHECKPOINT_ANALYSIS_DEDUP_HOURS = 24
"""Minimum hours between AI analyses of the same checkpoint"""

# ============================================================================
# GDPR DATA RETENTION
# ============================================================================
ANONYMIZED_PLACEHOLDER = "[anonymized]"
"""Replaces free-text fields once a record passes the retention cutoff.

Shared by the retention task that writes it and by read paths that must filter
such records out — if the two ever disagree, anonymized rows leak to the UI.
"""

# ============================================================================
# RATE LIMITING
# ============================================================================
RATELIMIT_API = "100 per minute"
"""Rate limit for API endpoints"""

RATELIMIT_AUTH = "10 per minute"
"""Rate limit for authentication endpoints"""

RATELIMIT_AI = "20 per minute"
"""Rate limit for AI-consuming endpoints"""

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
