"""
Financial Data Service

Main service for accessing financial data across the platform.
Provides configured provider with caching.

Usage:
    from app.services.financial_data import FinancialDataService

    service = FinancialDataService()
    price = service.get_historical_price('AAPL', date(2024, 1, 31))
"""

import logging
from typing import Optional, Dict, Any
from datetime import date

from .providers import (
    FinancialDataProvider,
    YahooFinanceProvider,
    CachedFinancialDataProvider
)

logger = logging.getLogger(__name__)


class FinancialDataService:
    """
    Financial data service with provider abstraction.

    By default uses Yahoo Finance with file-based caching.
    Provider can be swapped by changing configuration.
    """

    _default_provider = None

    def __init__(self, provider: Optional[FinancialDataProvider] = None):
        """
        Initialize financial data service.

        Args:
            provider: Custom provider (default: cached Yahoo Finance)
        """
        if provider is not None:
            self.provider = provider
        else:
            # Use default provider (lazy initialization)
            if FinancialDataService._default_provider is None:
                FinancialDataService._default_provider = self._create_default_provider()
            self.provider = FinancialDataService._default_provider

    def _create_default_provider(self) -> FinancialDataProvider:
        """
        Create default provider (Yahoo Finance with caching).

        Returns:
            Configured provider
        """
        # Base provider: Yahoo Finance
        base_provider = YahooFinanceProvider()

        # Wrap with caching (historical prices cached forever)
        cached_provider = CachedFinancialDataProvider(base_provider)

        logger.info(f"Financial data service initialized with {cached_provider.provider_name}")
        return cached_provider

    # ============================================================
    # Public API (delegates to provider)
    # ============================================================

    def get_current_price(self, ticker: str) -> Optional[float]:
        """
        Get current price for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Current price, or None if unavailable
        """
        return self.provider.get_current_price(ticker)

    def get_current_price_with_currency(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get current price with currency.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dict with 'price' and 'currency', or None if unavailable
        """
        return self.provider.get_current_price_with_currency(ticker)

    def get_historical_price(
        self,
        ticker: str,
        price_date: date
    ) -> Optional[float]:
        """
        Get historical price for a specific date.

        Args:
            ticker: Stock ticker symbol
            price_date: Date to fetch price for

        Returns:
            Close price, or None if unavailable
        """
        return self.provider.get_historical_price(ticker, price_date)

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
            start_date: Start of range
            end_date: End of range

        Returns:
            Dict mapping date -> close_price
        """
        return self.provider.get_historical_prices_bulk(ticker, start_date, end_date)

    def get_historical_prices_multi(
        self,
        tickers: list[str],
        price_dates: list[date]
    ) -> Dict[str, Dict[date, float]]:
        """
        Get historical prices for multiple tickers on specific dates.

        Efficiently fetches prices by batching requests.

        Args:
            tickers: List of stock ticker symbols
            price_dates: List of dates to fetch prices for

        Returns:
            Dict mapping ticker -> {date -> price}
            Example: {'AAPL': {date(2024,1,31): 185.50}, 'GOOGL': {date(2024,1,31): 145.20}}
        """
        if not tickers or not price_dates:
            return {}

        result = {}

        # Determine date range
        start_date = min(price_dates)
        end_date = max(price_dates)

        # Fetch each ticker
        for ticker in tickers:
            # Fetch full range for this ticker (provider caches it)
            all_prices = self.provider.get_historical_prices_bulk(ticker, start_date, end_date)

            # Filter to only requested dates
            ticker_prices = {
                price_date: all_prices[price_date]
                for price_date in price_dates
                if price_date in all_prices
            }

            result[ticker] = ticker_prices

        return result

    def get_ticker_info(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get company information for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dict with company info, or None if unavailable
        """
        return self.provider.get_ticker_info(ticker)

    @property
    def provider_name(self) -> str:
        """Get current provider name"""
        return self.provider.provider_name

    def is_available(self) -> bool:
        """Check if provider is available"""
        return self.provider.is_available()
