"""
Centralized time utilities for the investment checklist platform.

This module provides consistent timezone handling across the entire application.
All time-related operations should use these utilities to ensure consistency.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional


# Configuration for the platform's timezone
# TODO: Make this configurable per user or from environment variables
PLATFORM_TIMEZONE_OFFSET_HOURS = 2  # UTC+2 (Central European Summer Time)


def now_utc() -> datetime:
    """
    Get the current time in UTC.

    Returns:
        datetime: Current time as timezone-aware UTC datetime
    """
    return datetime.now(timezone.utc)


def ensure_timezone_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Convert timezone-naive datetime to timezone-aware UTC datetime.

    This function handles the platform's specific timezone conversion logic.
    Database-stored timezone-naive datetimes are assumed to be in local time
    and are converted to UTC.

    Args:
        dt: Datetime object (can be timezone-naive or timezone-aware, or None)

    Returns:
        datetime: Timezone-aware UTC datetime, or None if input was None
    """
    if dt is None:
        return None

    if dt.tzinfo is None:
        # Timezone-naive datetime is assumed to be in platform's local time
        # Convert from local time to UTC by subtracting the offset
        dt_utc = dt - timedelta(hours=PLATFORM_TIMEZONE_OFFSET_HOURS)
        return dt_utc.replace(tzinfo=timezone.utc)

    # Already timezone-aware, return as-is
    return dt


def calculate_duration_minutes(start_time: datetime, end_time: datetime) -> int:
    """
    Calculate duration between two datetime objects in minutes.

    Handles timezone conversion automatically to ensure accurate calculations.

    Args:
        start_time: Start datetime (timezone-aware or naive)
        end_time: End datetime (timezone-aware or naive)

    Returns:
        int: Duration in minutes (always non-negative)
    """
    start_aware = ensure_timezone_aware(start_time)
    end_aware = ensure_timezone_aware(end_time)

    if start_aware is None or end_aware is None:
        return 0

    duration_seconds = (end_aware - start_aware).total_seconds()
    return max(0, int(duration_seconds / 60))  # Ensure non-negative


def format_for_javascript(dt: datetime) -> str:
    """
    Format datetime for JavaScript consumption with proper timezone handling.

    Args:
        dt: Datetime object to format

    Returns:
        str: ISO format string that JavaScript can parse correctly
    """
    dt_aware = ensure_timezone_aware(dt)
    if dt_aware is None:
        return ""

    return dt_aware.isoformat()


def hours_from_minutes(minutes: Optional[int]) -> float:
    """
    Convert minutes to hours with proper handling of None values.

    Args:
        minutes: Duration in minutes (can be None)

    Returns:
        float: Duration in hours (0.0 if input was None)
    """
    if minutes is None:
        return 0.0
    return minutes / 60.0