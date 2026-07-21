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
Financial Data Service

Main service for accessing financial data across the platform.
Provides configured provider with caching.

Usage:
    from app.services.financial_data import FinancialDataService

    service = FinancialDataService()
    price = service.get_historical_price('AAPL', date(2024, 1, 31))
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import date
from decimal import Decimal

from .providers import (
    FinancialDataProvider,
    YahooFinanceProvider,
    CachedFinancialDataProvider
)
from app.services.currency_service import CurrencyService
from app.utils.company_identity import company_identity_key, is_tradeable_equity

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

    def get_price_in_currency(self, ticker: str, target_currency: str) -> Optional[Dict[str, Any]]:
        """
        Fetch current price for a ticker and convert to target currency.

        Reusable across the platform wherever a price needs to be displayed
        in the user's preferred currency.

        Args:
            ticker: Stock ticker symbol (e.g., 'DECK', 'SAP.DE')
            target_currency: ISO currency code to convert to (e.g., 'EUR', 'USD')

        Returns:
            Dict with conversion details, or None if unavailable:
            {
                'price_native': float,       # Price in stock's native currency
                'currency_native': str,       # Native currency code (e.g., 'USD')
                'price_converted': float,     # Price in target currency
                'currency_target': str,       # Target currency code
                'exchange_rate': float,        # Rate used for conversion
                'same_currency': bool          # True if no conversion needed
            }
        """
        try:
            price_data = self.get_current_price_with_currency(ticker)
            if not price_data:
                return None

            native_price = price_data['price']
            native_currency = price_data['currency']

            if native_currency == target_currency:
                return {
                    'price_native': native_price,
                    'currency_native': native_currency,
                    'price_converted': native_price,
                    'currency_target': target_currency,
                    'exchange_rate': 1.0,
                    'same_currency': True,
                }

            exchange_rate = CurrencyService.get_exchange_rate(
                from_currency=native_currency,
                to_currency=target_currency,
            )
            converted_price = float(Decimal(str(native_price)) * exchange_rate)

            return {
                'price_native': native_price,
                'currency_native': native_currency,
                'price_converted': converted_price,
                'currency_target': target_currency,
                'exchange_rate': float(exchange_rate),
                'same_currency': False,
            }

        except Exception as e:
            logger.error("Error fetching price in currency for %s -> %s: %s", ticker, target_currency, e)
            return None

    def get_ticker_info(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get company information for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dict with company info, or None if unavailable
        """
        return self.provider.get_ticker_info(ticker)

    def search_companies(self, query: str, max_results: int = 5) -> list[Dict[str, Any]]:
        """
        Search for companies by name or ticker, one entry per company.

        Providers return every listing they know of, so a search for
        "Microsoft" comes back as MSFT, MSF.F, MSFT.NE, ZMSF.NE and a tokenized
        crypto product -- which read as duplicates to a user. This collapses
        them to the company's primary listing and drops instruments that are
        not equity in the company itself.

        Args:
            query: Search query (company name or partial ticker)
            max_results: Maximum number of companies to return

        Returns:
            List of company info dicts, each containing:
            - ticker_symbol: Stock ticker
            - name: Company name
            - exchange: Exchange name (optional)
            - sector: Sector (optional)
            - industry: Industry (optional)
            - quote_type: Instrument type, e.g. 'EQUITY' (optional)
            - score: Provider relevance score, higher is better (optional)
        """
        # Over-fetch: collapsing cross-listings can discard most of a page of
        # results, and we still want max_results distinct companies.
        raw_results = self.provider.search_companies(query, max_results * 4)

        companies = []
        seen_identities = set()

        for result in raw_results:
            if not result.get('ticker_symbol'):
                continue

            if not is_tradeable_equity(result):
                continue

            identity = company_identity_key(
                result.get('name'), result.get('ticker_symbol')
            )
            if not identity or identity in seen_identities:
                continue

            # Providers return results in relevance order, so the first listing
            # seen for a company is its primary one.
            seen_identities.add(identity)
            companies.append(result)

            if len(companies) >= max_results:
                break

        return companies

    def get_batch_current_prices(self, tickers: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Get current prices with currency for multiple tickers.

        Args:
            tickers: List of stock ticker symbols

        Returns:
            Dict mapping ticker -> {'price': float, 'currency': str} or None
        """
        return self.provider.get_batch_current_prices(tickers)

    def get_exchange_rate(self, from_currency: str, to_currency: str) -> Optional[Decimal]:
        """
        Get current exchange rate between two currencies.

        Args:
            from_currency: Source currency code (e.g., 'EUR')
            to_currency: Target currency code (e.g., 'USD')

        Returns:
            Exchange rate as Decimal, or None if unavailable
        """
        return self.provider.get_exchange_rate(from_currency, to_currency)

    def get_valuation_metrics(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get valuation metrics (PE, EPS, price) for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dict with valuation data, or None if unavailable
        """
        return self.provider.get_valuation_metrics(ticker)

    def validate_ticker(self, ticker: str) -> Dict[str, Any]:
        """
        Validate a ticker symbol against the provider.

        Args:
            ticker: Stock ticker to validate

        Returns:
            Dict with validation results
        """
        return self.provider.validate_ticker(ticker)

    def get_financial_statements(self, ticker: str, years: int = 5) -> Optional[Dict[str, Any]]:
        """
        Get historical financial statements.

        Args:
            ticker: Stock ticker symbol
            years: Number of years of data to fetch

        Returns:
            Dict with 'income_statement', 'balance_sheet', 'cash_flow' DataFrames
        """
        return self.provider.get_financial_statements(ticker, years)

    @property
    def provider_name(self) -> str:
        """Get current provider name"""
        return self.provider.provider_name

    def is_available(self) -> bool:
        """Check if provider is available"""
        return self.provider.is_available()
