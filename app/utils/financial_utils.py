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
Financial calculation utilities
Common functions for portfolio analytics and performance tracking
"""

from decimal import Decimal
from typing import Union, Optional, Dict
from datetime import date


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


# ============================================================
# Historical Price Functions (Provider-Agnostic)
# ============================================================

def get_historical_price(ticker: str, price_date: date) -> Optional[float]:
    """
    Get historical close price for a ticker on a specific date.

    Uses configured financial data provider (Yahoo Finance by default).
    Results are cached (history never changes!).

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'GOOGL')
        price_date: Date to fetch price for

    Returns:
        Close price as float, or None if unavailable

    Example:
        >>> from datetime import date
        >>> price = get_historical_price('AAPL', date(2024, 1, 31))
        >>> print(f"${price:.2f}")
        $185.50
    """
    from app.services.financial_data import FinancialDataService

    service = FinancialDataService()
    return service.get_historical_price(ticker, price_date)


def get_historical_prices_bulk(
    ticker: str,
    start_date: date,
    end_date: date
) -> Dict[date, float]:
    """
    Get historical prices for a ticker over a date range.

    Efficient bulk fetch with caching.

    Args:
        ticker: Stock ticker symbol
        start_date: Start of date range (inclusive)
        end_date: End of date range (inclusive)

    Returns:
        Dict mapping date -> close_price
        Only includes dates where data is available (skips weekends/holidays)

    Example:
        >>> from datetime import date
        >>> prices = get_historical_prices_bulk('AAPL', date(2024, 1, 1), date(2024, 1, 31))
        >>> print(f"{len(prices)} trading days")
        21 trading days
    """
    from app.services.financial_data import FinancialDataService

    service = FinancialDataService()
    return service.get_historical_prices_bulk(ticker, start_date, end_date)


def get_historical_prices_multi(
    tickers: list[str],
    price_dates: list[date]
) -> Dict[str, Dict[date, float]]:
    """
    Get historical prices for multiple tickers on specific dates.

    Optimized for portfolio performance charts where you need prices
    for multiple stocks on the same set of dates.

    Args:
        tickers: List of stock ticker symbols
        price_dates: List of dates to fetch prices for

    Returns:
        Dict mapping ticker -> {date -> price}

    Example:
        >>> from datetime import date
        >>> tickers = ['AAPL', 'GOOGL', 'MSFT']
        >>> dates = [date(2024, 1, 31), date(2024, 2, 29)]
        >>> prices = get_historical_prices_multi(tickers, dates)
        >>> print(prices['AAPL'][date(2024, 1, 31)])
        185.50
    """
    from app.services.financial_data import FinancialDataService

    service = FinancialDataService()
    return service.get_historical_prices_multi(tickers, price_dates)
