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

# TODO: Is this correct place?
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

    Naive datetimes from the database are assumed to be in UTC
    (stored via now_utc()). They are tagged as UTC directly without
    any local-time offset conversion.

    Args:
        dt: Datetime object to format

    Returns:
        str: ISO format string that JavaScript can parse correctly
    """
    if dt is None:
        return ""

    if dt.tzinfo is None:
        # Database stores UTC values as naive datetimes (via now_utc()).
        # Attach UTC tzinfo directly — do NOT treat as local time.
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.isoformat()


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


def parse_date_string(
    date_str: str,
    format_str: str = '%Y-%m-%d',
    default: Optional[datetime] = None
) -> Optional[datetime]:
    """
    Parse date string with error handling.

    Args:
        date_str: Date string to parse
        format_str: Format string (default: '%Y-%m-%d')
        default: Value to return if parsing fails (default: None)

    Returns:
        datetime object if parsing succeeds, default value otherwise

    Example:
        >>> parse_date_string('2024-01-15')
        datetime.date(2024, 1, 15)
        >>> parse_date_string('invalid')
        None
        >>> parse_date_string('2024/01/15', format_str='%Y/%m/%d')
        datetime.date(2024, 1, 15)
    """
    if not date_str:
        return default

    try:
        return datetime.strptime(date_str, format_str)
    except (ValueError, TypeError):
        return default


def parse_date_to_date_object(
    date_str: str,
    format_str: str = '%Y-%m-%d',
    default: Optional[datetime] = None
):
    """
    Parse date string and return date object (not datetime).

    Args:
        date_str: Date string to parse
        format_str: Format string (default: '%Y-%m-%d')
        default: Value to return if parsing fails (default: None)

    Returns:
        date object if parsing succeeds, default value otherwise

    Example:
        >>> parse_date_to_date_object('2024-01-15')
        date(2024, 1, 15)
        >>> parse_date_to_date_object('invalid')
        None
    """
    dt = parse_date_string(date_str, format_str, default)
    return dt.date() if dt else default


def safe_parse_date_range(
    start_date_str: Optional[str],
    end_date_str: Optional[str],
    format_str: str = '%Y-%m-%d'
) -> tuple[Optional[datetime], Optional[datetime]]:
    """
    Parse start and end date strings with error handling.

    Args:
        start_date_str: Start date string
        end_date_str: End date string
        format_str: Format string for both dates

    Returns:
        Tuple of (start_date, end_date), with None for unparseable dates

    Example:
        >>> safe_parse_date_range('2024-01-01', '2024-12-31')
        (date(2024, 1, 1), date(2024, 12, 31))
        >>> safe_parse_date_range('invalid', '2024-12-31')
        (None, date(2024, 12, 31))
    """
    start_date = parse_date_to_date_object(start_date_str, format_str) if start_date_str else None
    end_date = parse_date_to_date_object(end_date_str, format_str) if end_date_str else None
    return start_date, end_date


def format_date(
    dt: Optional[datetime],
    format_str: str = '%Y-%m-%d',
    default: str = ''
) -> str:
    """
    Format datetime/date object to string with safe handling.

    Args:
        dt: Datetime or date object to format
        format_str: Format string
        default: String to return if dt is None

    Returns:
        Formatted date string or default

    Example:
        >>> format_date(datetime(2024, 1, 15))
        '2024-01-15'
        >>> format_date(None, default='N/A')
        'N/A'
    """
    if dt is None:
        return default

    try:
        return dt.strftime(format_str)
    except (ValueError, AttributeError):
        return default


def days_between(
    start_date: datetime,
    end_date: Optional[datetime] = None
) -> int:
    """
    Calculate number of days between two dates.

    Args:
        start_date: Start date
        end_date: End date (defaults to today if None)

    Returns:
        Number of days between dates (always non-negative)

    Example:
        >>> days_between(datetime(2024, 1, 1), datetime(2024, 1, 15))
        14
    """
    if end_date is None:
        end_date = now_utc()

    delta = end_date - start_date
    return abs(delta.days)