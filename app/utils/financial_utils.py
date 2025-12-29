"""
Financial calculation utilities
Common functions for portfolio analytics and performance tracking
"""

from decimal import Decimal
from typing import Union


def calculate_cagr(
    total_return_pct: Union[float, Decimal],
    days_held: int,
    min_days_for_annualization: int = 30
) -> float:
    """
    Calculate Compound Annual Growth Rate (CAGR).

    CAGR normalizes returns to an annual basis, making it easier to compare
    investments held for different time periods.

    Formula: CAGR = ((1 + Total Return) ^ (1 / Years)) - 1

    Args:
        total_return_pct: Total return percentage (e.g., 25.5 for 25.5%)
        days_held: Number of days the investment has been held
        min_days_for_annualization: Minimum days before annualizing (default: 30)
                                   For very short periods, annualizing can be misleading

    Returns:
        Annualized return percentage (CAGR)

    Examples:
        >>> calculate_cagr(25.0, 365)  # 25% return over 1 year
        25.0

        >>> calculate_cagr(25.0, 730)  # 25% return over 2 years
        11.8

        >>> calculate_cagr(15.0, 15)  # 15% return in 15 days (< 30 days)
        15.0  # Returns actual return without annualizing
    """
    if days_held == 0:
        return 0.0

    # For very short holding periods, return the actual return
    # Annualizing a 5% return over 2 weeks to 130% is misleading
    if days_held < min_days_for_annualization:
        return float(total_return_pct)

    # Convert to years
    years_held = days_held / 365.25

    # Convert percentage to decimal (e.g., 25.5% -> 0.255)
    total_return_decimal = float(total_return_pct) / 100.0

    try:
        # Calculate CAGR: ((1 + total_return) ^ (1 / years)) - 1
        # Then convert back to percentage
        cagr = ((1 + total_return_decimal) ** (1 / years_held) - 1) * 100
        return round(cagr, 2)
    except (ValueError, ZeroDivisionError, OverflowError):
        # If calculation fails (e.g., extreme negative returns with fractional exponent),
        # return total return as fallback
        return float(total_return_pct)


def calculate_annualized_return(
    total_return_pct: Union[float, Decimal],
    days_held: int
) -> float:
    """
    Alias for calculate_cagr for backward compatibility.

    Args:
        total_return_pct: Total return percentage
        days_held: Number of days held

    Returns:
        Annualized return percentage (CAGR)
    """
    return calculate_cagr(total_return_pct, days_held)


def calculate_total_return(
    initial_value: Union[float, Decimal],
    final_value: Union[float, Decimal]
) -> float:
    """
    Calculate total return percentage.

    Args:
        initial_value: Initial investment value
        final_value: Current/final investment value

    Returns:
        Total return percentage

    Example:
        >>> calculate_total_return(1000, 1250)
        25.0
    """
    if not initial_value or initial_value == 0:
        return 0.0

    return round(((float(final_value) - float(initial_value)) / float(initial_value)) * 100, 2)


def format_return_display(
    return_pct: Union[float, Decimal],
    include_sign: bool = True
) -> str:
    """
    Format a return percentage for display.

    Args:
        return_pct: Return percentage to format
        include_sign: Whether to include + sign for positive returns

    Returns:
        Formatted string (e.g., "+25.3%" or "-12.5%")

    Example:
        >>> format_return_display(25.3)
        '+25.3%'

        >>> format_return_display(-12.5)
        '-12.5%'
    """
    value = float(return_pct)
    sign = '+' if value >= 0 and include_sign else ''
    return f"{sign}{value:.1f}%"
