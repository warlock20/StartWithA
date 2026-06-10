# Investment Checklist Platform
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
Yahoo Finance Provider Implementation

Uses yfinance library to fetch stock prices and company data.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import date, timedelta
from decimal import Decimal
import yfinance as yf

from app.services.currency_service import CurrencyService
from .base import FinancialDataProvider
logger = logging.getLogger(__name__)


class YahooFinanceProvider(FinancialDataProvider):
    """
    Yahoo Finance data provider.

    Fetches current prices, historical prices, and company info from Yahoo Finance.
    No caching - pure API provider (caching handled by wrapper).
    """

    def __init__(self):
        """Initialize Yahoo Finance provider"""
        self._available = True

    @property
    def provider_name(self) -> str:
        """Get provider name"""
        return "yahoo_finance"

    def is_available(self) -> bool:
        """Check if Yahoo Finance is available"""
        return self._available

    def get_current_price(self, ticker: str) -> Optional[float]:
        """
        Fetch current price from Yahoo Finance.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Current price, or None if error
        """
        try:
            ticker_obj = yf.Ticker(ticker)
            info = ticker_obj.info

            # Try multiple price fields (Yahoo Finance API can be inconsistent)
            price = (
                info.get('currentPrice') or
                info.get('regularMarketPrice') or
                info.get('previousClose')
            )

            if price is None:
                logger.warning(f"No price data available for {ticker}")
                return None

            return float(price)

        except Exception as e:
            logger.error(f"Error fetching current price for {ticker}: {str(e)}")
            return None

    def get_current_price_with_currency(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Fetch current price AND currency from Yahoo Finance.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dict with 'price' and 'currency', or None if error
        """
        try:
            ticker_obj = yf.Ticker(ticker)
            info = ticker_obj.info

            # Get price
            price = (
                info.get('currentPrice') or
                info.get('regularMarketPrice') or
                info.get('previousClose')
            )

            if price is None:
                logger.warning(f"No price data available for {ticker}")
                return None

            # Get currency from Yahoo Finance and normalize sub-units (e.g., GBp → GBP)
            raw_currency = info.get('currency', '')
            price_float = float(price)

            if not raw_currency or raw_currency.upper() == 'NONE':
                currency = CurrencyService.detect_currency_from_ticker(ticker)
            else:
                currency, price_float = CurrencyService.normalize_yahoo_currency(
                    raw_currency, price_float
                )

            return {
                'price': price_float,
                'currency': currency
            }

        except Exception as e:
            logger.error(f"Error fetching price with currency for {ticker}: {str(e)}")
            return None

    def get_historical_price(
        self,
        ticker: str,
        price_date: date
    ) -> Optional[float]:
        """
        Get close price for a specific date.

        Fetches a 3-day window around target date to handle weekends/holidays.
        Returns None if data is unavailable (conservative approach).

        Args:
            ticker: Stock ticker symbol
            price_date: Date to fetch price for

        Returns:
            Close price, or None if unavailable
        """
        try:
            # Fetch 3-day window around target date (handles weekends/holidays)
            start = price_date - timedelta(days=3)
            end = price_date + timedelta(days=1)

            ticker_obj = yf.Ticker(ticker)
            hist = ticker_obj.history(start=start, end=end)

            if hist.empty:
                logger.warning(f"No historical data for {ticker} around {price_date}")
                return None

            # Get closest available date to target
            closest_date = min(hist.index, key=lambda d: abs(d.date() - price_date))

            # Only accept if within 3-day window
            if abs((closest_date.date() - price_date).days) > 3:
                logger.warning(f"No price for {ticker} within 3 days of {price_date}")
                return None

            close_price = float(hist.loc[closest_date]['Close'])
            logger.debug(f"Historical price for {ticker} on {price_date}: ${close_price}")

            return close_price

        except Exception as e:
            logger.error(f"Error fetching historical price for {ticker} on {price_date}: {str(e)}")
            return None

    def get_historical_prices_bulk(
        self,
        ticker: str,
        start_date: date,
        end_date: date
    ) -> Dict[date, float]:
        """
        Get historical prices over a date range.

        Single API call for efficiency.

        Args:
            ticker: Stock ticker symbol
            start_date: Start of range (inclusive)
            end_date: End of range (inclusive)

        Returns:
            Dict mapping date -> close_price
        """
        try:
            ticker_obj = yf.Ticker(ticker)
            hist = ticker_obj.history(start=start_date, end=end_date)

            if hist.empty:
                logger.warning(f"No historical data for {ticker} from {start_date} to {end_date}")
                return {}

            # Convert to dict {date: price}
            prices = {}
            for timestamp, row in hist.iterrows():
                price_date = timestamp.date()
                prices[price_date] = float(row['Close'])

            logger.info(f"Fetched {len(prices)} historical prices for {ticker}")
            return prices

        except Exception as e:
            logger.error(f"Error fetching bulk historical prices for {ticker}: {str(e)}")
            return {}

    def get_ticker_info(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get company information from Yahoo Finance.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dict with company info, or None if unavailable
        """
        try:
            ticker_obj = yf.Ticker(ticker)
            info = ticker_obj.info

            return {
                'name': info.get('longName') or info.get('shortName'),
                'currency': info.get('currency', 'USD').upper(),
                'exchange': info.get('exchange'),
                'sector': info.get('sector'),
                'industry': info.get('industry'),
                'market_cap': info.get('marketCap'),
                'country': info.get('country')
            }

        except Exception as e:
            logger.error(f"Error fetching ticker info for {ticker}: {str(e)}")
            return None

    def get_valuation_metrics(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get valuation metrics (PE, EPS, price) from Yahoo Finance.
        Used by the Intelligence Panel for on-demand calculations.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dict with valuation data, or None if unavailable
        """
        try:
            ticker_obj = yf.Ticker(ticker)
            info = ticker_obj.info

            price = (
                info.get('currentPrice') or
                info.get('regularMarketPrice') or
                info.get('previousClose')
            )

            return {
                'pe_ratio': info.get('trailingPE'),
                'eps_ttm': info.get('trailingEps'),
                'forward_pe': info.get('forwardPE'),
                'forward_eps': info.get('forwardEps'),
                'current_price': float(price) if price else None,
                'sector': info.get('sector'),
                'industry': info.get('industry'),
                'currency': CurrencyService.normalize_yahoo_currency(
                    info.get('currency', ''), 0
                )[0] or CurrencyService.detect_currency_from_ticker(ticker),
            }

        except Exception as e:
            logger.error(f"Error fetching valuation metrics for {ticker}: {str(e)}")
            return None

    def get_batch_current_prices(self, tickers: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Get current prices with currency for multiple tickers.

        Uses the same yf.Ticker().info API as get_current_price_with_currency()
        to ensure consistent prices across individual and batch calls.

        Args:
            tickers: List of stock ticker symbols

        Returns:
            Dict mapping ticker -> {'price': float, 'currency': str} or None
        """
        results = {}
        for ticker in tickers:
            results[ticker] = self.get_current_price_with_currency(ticker)
        return results

    def get_exchange_rate(self, from_currency: str, to_currency: str) -> Optional[Decimal]:
        """
        Fetch current exchange rate from Yahoo Finance.

        Args:
            from_currency: Source currency (e.g., 'EUR')
            to_currency: Target currency (e.g., 'USD')

        Returns:
            Exchange rate as Decimal, or None if unavailable
        """
        if from_currency == to_currency:
            return Decimal('1.0')

        fx_ticker = f"{from_currency.upper()}{to_currency.upper()}=X"

        try:
            ticker = yf.Ticker(fx_ticker)
            info = ticker.info

            rate = (
                info.get('regularMarketPrice') or
                info.get('currentPrice') or
                info.get('previousClose')
            )

            if rate is None:
                logger.warning(f"No exchange rate data for {fx_ticker}")
                return None

            return Decimal(str(rate))

        except Exception as e:
            logger.error(f"Error fetching exchange rate for {fx_ticker}: {str(e)}")
            return None

    def validate_ticker(self, ticker: str) -> Dict[str, Any]:
        """
        Validate a ticker symbol against Yahoo Finance.

        Args:
            ticker: Stock ticker to validate

        Returns:
            Dict with validation results
        """
        result = {
            'valid': False,
            'ticker': ticker.upper() if ticker else '',
            'error': None,
            'company_name': None,
            'current_price': None,
            'exchange': None,
            'currency': None
        }

        if not ticker or not ticker.strip():
            result['error'] = 'Ticker symbol is required'
            return result

        ticker = ticker.strip().upper()
        result['ticker'] = ticker

        if len(ticker) > 20:
            result['error'] = 'Ticker too long (max 20 characters)'
            return result

        try:
            ticker_obj = yf.Ticker(ticker)
            info = ticker_obj.info

            if not info or 'symbol' not in info:
                result['error'] = f'Ticker "{ticker}" not found on Yahoo Finance'
                return result

            company_name = (
                info.get('longName') or
                info.get('shortName') or
                info.get('symbol')
            )

            current_price = (
                info.get('currentPrice') or
                info.get('regularMarketPrice') or
                info.get('previousClose')
            )

            exchange = info.get('exchange') or info.get('market')

            raw_currency = info.get('currency') or ''
            price_float = float(current_price) if current_price else None

            if raw_currency and raw_currency.upper() != 'NONE':
                currency, price_float = CurrencyService.normalize_yahoo_currency(
                    raw_currency, price_float
                )
            else:
                currency = None

            if company_name:
                result['valid'] = True
                result['company_name'] = company_name
                result['current_price'] = price_float
                result['exchange'] = exchange
                result['currency'] = currency
            else:
                result['error'] = f'Unable to retrieve information for "{ticker}"'

        except Exception as e:
            logger.error(f"Error validating ticker {ticker}: {str(e)}")
            result['error'] = f'Error validating ticker: {str(e)}'

        return result

    def get_financial_statements(self, ticker: str, years: int = 5) -> Optional[Dict[str, Any]]:
        """
        Get historical financial statements from Yahoo Finance.

        Args:
            ticker: Stock ticker symbol
            years: Number of years of data to fetch

        Returns:
            Dict with 'income_statement', 'balance_sheet', 'cash_flow' DataFrames,
            or None if unavailable
        """
        try:
            ticker_obj = yf.Ticker(ticker)

            income_stmt = ticker_obj.income_stmt
            balance_sheet = ticker_obj.balance_sheet
            cashflow = ticker_obj.cashflow

            # Limit to requested years
            if not income_stmt.empty:
                income_stmt = income_stmt.iloc[:, :years]
            if not balance_sheet.empty:
                balance_sheet = balance_sheet.iloc[:, :years]
            if not cashflow.empty:
                cashflow = cashflow.iloc[:, :years]

            return {
                'income_statement': income_stmt,
                'balance_sheet': balance_sheet,
                'cash_flow': cashflow
            }

        except Exception as e:
            logger.error(f"Error fetching financial statements for {ticker}: {str(e)}")
            return None

    def search_companies(self, query: str, max_results: int = 5) -> list[Dict[str, Any]]:
        """
        Search for companies by name or ticker using Yahoo Finance.

        Args:
            query: Search query (company name or partial ticker)
            max_results: Maximum number of results to return

        Returns:
            List of company info dicts
        """
        results = []

        try:
            # Suppress yfinance HTTP errors during search
            logging.getLogger('yfinance').setLevel(logging.CRITICAL)

            search_results = yf.Search(query, max_results=max_results, news_count=0)

            if search_results and hasattr(search_results, 'quotes') and search_results.quotes:
                for result in search_results.quotes[:max_results]:
                    ticker_symbol = result.get('symbol')
                    if not ticker_symbol:
                        continue

                    # Extract name from various possible fields
                    company_name = (
                        result.get('longname') or
                        result.get('shortname') or
                        result.get('name') or
                        result.get('longName') or
                        result.get('shortName') or
                        ticker_symbol
                    )

                    results.append({
                        'ticker_symbol': ticker_symbol,
                        'name': company_name,
                        'exchange': result.get('exchange') or result.get('exchDisp'),
                        'sector': result.get('sector') or result.get('sectorDisp'),
                        'industry': result.get('industry') or result.get('industryDisp'),
                    })

            # Restore logging level
            logging.getLogger('yfinance').setLevel(logging.WARNING)

        except Exception as e:
            logger.error(f"Error searching for '{query}': {str(e)}")
            logging.getLogger('yfinance').setLevel(logging.WARNING)

        return results
