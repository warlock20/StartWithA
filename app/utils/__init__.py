"""
Utility modules for the investment checklist platform.

This package contains shared utilities used across the application.
"""

from .time_utils import (
    now_utc,
    ensure_timezone_aware,
    calculate_duration_minutes,
    format_for_javascript,
    hours_from_minutes,
)

__all__ = [
    'now_utc',
    'ensure_timezone_aware',
    'calculate_duration_minutes',
    'format_for_javascript',
    'hours_from_minutes',
]