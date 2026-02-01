"""
Abstract Base Class for Financial Data Providers

This module defines the interface that all financial data providers must implement.
This allows easy swapping between providers (Yahoo Finance, Alpha Vantage, Polygon, etc.)
without changing the service layer code.

Usage:
    from app.services.financial_data.providers.base import FinancialDataProvider

    class MyProvider(FinancialDataProvider):
        def get_current_price(self, ticker):
            # Implementation
            pass
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from datetime import date


class FinancialDataProvider(ABC):
    """
    Abstract interface for financial data providers.

    All financial data providers (Yahoo Finance, Alpha Vantage, etc.) must implement
    this interface to ensure consistent behavior across the platform.
    """

    @abstractmethod
    def get_current_price(self, ticker: str) -> Optional[float]:
        """
        Get current/latest price for a ticker.

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL', 'GOOGL')

        Returns:
            Current price as float, or None if unavailable

        Raises:
            Exception: For API errors
        """
        pass

    @abstractmethod
    def get_current_price_with_currency(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get current price AND currency for a ticker.

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL', 'SAP.DE')

        Returns:
            Dict with 'price' and 'currency', or None if unavailable
            Example: {'price': 185.50, 'currency': 'USD'}

        Raises:
            Exception: For API errors
        """
        pass

    @abstractmethod
    def get_historical_price(
        self,
        ticker: str,
        price_date: date
    ) -> Optional[float]:
        """
        Get close price for a specific date.

        Args:
            ticker: Stock ticker symbol
            price_date: Date to fetch price for

        Returns:
            Close price as float, or None if unavailable

        Note:
            Returns None for:
            - Market closed on that date
            - Ticker didn't exist yet
            - Data unavailable from provider
        """
        pass

    @abstractmethod
    def get_historical_prices_bulk(
        self,
        ticker: str,
        start_date: date,
        end_date: date
    ) -> Dict[date, float]:
        """
        Get historical prices over a date range.

        Args:
            ticker: Stock ticker symbol
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)

        Returns:
            Dict mapping date -> close_price
            Example: {date(2024, 1, 31): 185.50, date(2024, 2, 29): 182.31}

        Note:
            Only includes dates where data is available.
            May not include weekends/holidays when market is closed.
        """
        pass

    @abstractmethod
    def get_ticker_info(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get company information for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dict with company info, or None if unavailable
            Example: {
                'name': 'Apple Inc.',
                'currency': 'USD',
                'exchange': 'NASDAQ',
                'sector': 'Technology'
            }
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """
        Get provider name for logging/debugging.

        Returns:
            Provider name (e.g., 'yahoo_finance', 'alpha_vantage')
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if provider is available (API key valid, service reachable, etc.).

        Returns:
            True if provider is ready to use
        """
        pass

    @abstractmethod
    def search_companies(self, query: str, max_results: int = 5) -> list[Dict[str, Any]]:
        """
        Search for companies by name or ticker.

        Args:
            query: Search query (company name or partial ticker)
            max_results: Maximum number of results to return

        Returns:
            List of company info dicts, each containing:
            - ticker_symbol: Stock ticker
            - name: Company name
            - exchange: Exchange name (optional)
            - sector: Sector (optional)
            - industry: Industry (optional)
        """
        pass
