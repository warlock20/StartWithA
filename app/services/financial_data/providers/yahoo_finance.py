"""
Yahoo Finance Provider Implementation

Uses yfinance library to fetch stock prices and company data.
"""

import logging
from typing import Optional, Dict, Any
from datetime import date, timedelta
import yfinance as yf

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
        from app.services.currency_service import CurrencyService

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

            # Get currency from Yahoo Finance
            yahoo_currency = info.get('currency', '').upper()

            # If Yahoo didn't provide currency, detect from ticker
            if not yahoo_currency or yahoo_currency == 'NONE':
                currency = CurrencyService.detect_currency_from_ticker(ticker)
            else:
                currency = yahoo_currency

            return {
                'price': float(price),
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
