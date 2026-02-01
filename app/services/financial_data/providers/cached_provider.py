"""
Cached Financial Data Provider

Wraps any FinancialDataProvider with file-based caching.
Historical prices are cached forever (history doesn't change!).
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import date

from .base import FinancialDataProvider
from app.utils.time_utils import now_utc

logger = logging.getLogger(__name__)


class CachedFinancialDataProvider(FinancialDataProvider):
    """
    Cached wrapper for financial data providers.

    Caches historical prices in file system (history never changes!).
    Current prices are NOT cached (always fetch fresh).

    Cache structure:
        instance/cache/historical_prices/
            AAPL_2024-01-31.json
            GOOGL_2024-02-29.json
    """

    def __init__(self, base_provider: FinancialDataProvider, cache_dir: Optional[Path] = None):
        """
        Initialize cached provider.

        Args:
            base_provider: Underlying provider to wrap (e.g., YahooFinanceProvider)
            cache_dir: Cache directory (default: instance/cache/historical_prices)
        """
        self.provider = base_provider

        # Setup cache directory
        if cache_dir is None:
            cache_dir = Path(__file__).parent.parent.parent.parent / "instance" / "cache" / "historical_prices"

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"CachedFinancialDataProvider initialized with {base_provider.provider_name}, cache: {self.cache_dir}")

    @property
    def provider_name(self) -> str:
        """Get provider name"""
        return f"cached_{self.provider.provider_name}"

    def is_available(self) -> bool:
        """Check if underlying provider is available"""
        return self.provider.is_available()

    def get_current_price(self, ticker: str) -> Optional[float]:
        """
        Get current price (NOT cached - always fresh).

        Args:
            ticker: Stock ticker symbol

        Returns:
            Current price from provider
        """
        return self.provider.get_current_price(ticker)

    def get_current_price_with_currency(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get current price with currency (NOT cached - always fresh).

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dict with price and currency from provider
        """
        return self.provider.get_current_price_with_currency(ticker)

    def get_historical_price(
        self,
        ticker: str,
        price_date: date
    ) -> Optional[float]:
        """
        Get historical price (WITH caching).

        History never changes - safe to cache forever!

        Args:
            ticker: Stock ticker symbol
            price_date: Date to fetch price for

        Returns:
            Close price (cached or fresh from provider)
        """
        # 1. Check cache
        cached_price = self._read_cache(ticker, price_date)
        if cached_price is not None:
            logger.debug(f"Cache HIT: {ticker} on {price_date} = ${cached_price}")
            return cached_price

        # 2. Fetch from provider
        logger.debug(f"Cache MISS: Fetching {ticker} on {price_date} from provider")
        price = self.provider.get_historical_price(ticker, price_date)

        # 3. Save to cache (history is immutable!)
        if price is not None:
            self._save_cache(ticker, price_date, price)

        return price

    def get_historical_prices_bulk(
        self,
        ticker: str,
        start_date: date,
        end_date: date
    ) -> Dict[date, float]:
        """
        Get historical prices over date range (WITH caching).

        Checks cache for each date, only fetches missing dates from provider.

        Args:
            ticker: Stock ticker symbol
            start_date: Start of range
            end_date: End of range

        Returns:
            Dict mapping date -> price
        """
        # 1. Check what's in cache
        cached_prices = {}
        missing_dates = []

        # Generate all dates in range (we'll check each one)
        current_date = start_date
        all_dates = []
        while current_date <= end_date:
            all_dates.append(current_date)
            current_date += timedelta(days=1)

        # Check cache for each date
        for price_date in all_dates:
            cached = self._read_cache(ticker, price_date)
            if cached is not None:
                cached_prices[price_date] = cached
            else:
                missing_dates.append(price_date)

        # 2. Fetch missing dates from provider (bulk call)
        if missing_dates:
            logger.info(f"Fetching {len(missing_dates)} missing dates for {ticker} from provider")
            fresh_prices = self.provider.get_historical_prices_bulk(ticker, start_date, end_date)

            # 3. Save new prices to cache
            for price_date, price in fresh_prices.items():
                if price_date not in cached_prices:
                    cached_prices[price_date] = price
                    self._save_cache(ticker, price_date, price)

        logger.info(f"Returning {len(cached_prices)} prices for {ticker} ({len(cached_prices) - len(missing_dates)} from cache)")
        return cached_prices

    def get_ticker_info(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get ticker info (NOT cached - info can change).

        Args:
            ticker: Stock ticker symbol

        Returns:
            Company info from provider
        """
        return self.provider.get_ticker_info(ticker)

    def search_companies(self, query: str, max_results: int = 5) -> list[Dict[str, Any]]:
        """
        Search for companies (NOT cached - results can change).

        Args:
            query: Search query
            max_results: Maximum results to return

        Returns:
            List of company info dicts from provider
        """
        return self.provider.search_companies(query, max_results)

    # ============================================================
    # Cache Management (Private)
    # ============================================================

    def _get_cache_path(self, ticker: str, price_date: date) -> Path:
        """Get cache file path for a ticker and date"""
        return self.cache_dir / f"{ticker}_{price_date}.json"

    def _read_cache(self, ticker: str, price_date: date) -> Optional[float]:
        """
        Read price from cache.

        Returns:
            Cached price, or None if not cached
        """
        cache_file = self._get_cache_path(ticker, price_date)

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
                return data.get('close')
        except Exception as e:
            logger.error(f"Error reading cache for {ticker} on {price_date}: {e}")
            return None

    def _save_cache(self, ticker: str, price_date: date, price: float):
        """
        Save price to cache.

        Args:
            ticker: Stock ticker
            price_date: Date
            price: Close price
        """
        cache_file = self._get_cache_path(ticker, price_date)

        try:
            cache_data = {
                'close': price,
                'cached_at': now_utc().isoformat(),
                'ticker': ticker,
                'date': price_date.isoformat()
            }

            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)

            logger.debug(f"Cached price for {ticker} on {price_date}: ${price}")

        except Exception as e:
            logger.error(f"Error saving cache for {ticker} on {price_date}: {e}")

    def clear_cache(self, ticker: Optional[str] = None):
        """
        Clear cache (useful for testing or if data is corrupted).

        Args:
            ticker: If provided, only clear cache for this ticker. Otherwise clear all.
        """
        if ticker:
            # Clear specific ticker
            pattern = f"{ticker}_*.json"
            count = 0
            for cache_file in self.cache_dir.glob(pattern):
                cache_file.unlink()
                count += 1
            logger.info(f"Cleared {count} cache files for {ticker}")
        else:
            # Clear all cache
            count = 0
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
                count += 1
            logger.info(f"Cleared {count} total cache files")


# Import timedelta for date arithmetic
from datetime import timedelta
