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

# app/services/currency_service.py

from datetime import timedelta, date
from decimal import Decimal
from app import db
from app.models.portfolio import ExchangeRate
from app.utils.time_utils import now_utc

class CurrencyService:
    """
    Service for currency detection, conversion, and exchange rate management.
    Handles multi-currency portfolio support with caching for performance.
    """

    # Map ticker exchange suffixes to ISO 4217 currency codes
    TICKER_CURRENCY_MAP = {
        # US Exchanges
        '': 'USD',           # No suffix = USA (NASDAQ, NYSE)

        # European - Euro
        '.DE': 'EUR',        # Germany (XETRA)
        '.PA': 'EUR',        # France (Euronext Paris)
        '.AS': 'EUR',        # Netherlands (Amsterdam)
        '.BR': 'EUR',        # Belgium (Brussels)
        '.MC': 'EUR',        # Spain (Madrid)
        '.MI': 'EUR',        # Italy (Milan)
        '.HE': 'EUR',        # Finland (Helsinki)

        # UK
        '.L': 'GBP',         # London Stock Exchange

        # Switzerland
        '.SW': 'CHF',        # Swiss Exchange (SIX)

        # Japan
        '.T': 'JPY',         # Tokyo Stock Exchange

        # Canada
        '.TO': 'CAD',        # Toronto Stock Exchange
        '.V': 'CAD',         # Canadian Venture Exchange

        # Asia Pacific
        '.HK': 'HKD',        # Hong Kong
        '.AX': 'AUD',        # Australia
        '.NS': 'INR',        # India (NSE)
        '.BO': 'INR',        # India (BSE)
        '.KS': 'KRW',        # South Korea
        '.SZ': 'CNY',        # China (Shenzhen)
        '.SS': 'CNY',        # China (Shanghai)

        # Scandinavia
        '.ST': 'SEK',        # Sweden (Stockholm)
        '.CO': 'DKK',        # Denmark (Copenhagen)
        '.OL': 'NOK',        # Norway (Oslo)

        # Others
        '.SA': 'SAR',        # Saudi Arabia
        '.TA': 'ILS',        # Israel (Tel Aviv)
        '.IS': 'TRY',        # Turkey (Istanbul)
        '.JO': 'ZAR',        # South Africa (Johannesburg)
    }

    # Currency display names
    CURRENCY_NAMES = {
        'USD': 'US Dollar',
        'EUR': 'Euro',
        'GBP': 'British Pound',
        'JPY': 'Japanese Yen',
        'CAD': 'Canadian Dollar',
        'AUD': 'Australian Dollar',
        'CHF': 'Swiss Franc',
        'CNY': 'Chinese Yuan',
        'HKD': 'Hong Kong Dollar',
        'INR': 'Indian Rupee',
        'KRW': 'South Korean Won',
        'SEK': 'Swedish Krona',
        'NOK': 'Norwegian Krone',
        'DKK': 'Danish Krone',
        'ZAR': 'South African Rand',
        'SAR': 'Saudi Riyal',
        'ILS': 'Israeli Shekel',
        'TRY': 'Turkish Lira',
    }

    # Currency symbols
    CURRENCY_SYMBOLS = {
        'USD': '$',
        'EUR': '€',
        'GBP': '£',
        'JPY': '¥',
        'CAD': 'C$',
        'AUD': 'A$',
        'CHF': 'CHF',
        'CNY': '¥',
        'HKD': 'HK$',
        'INR': '₹',
        'KRW': '₩',
        'SEK': 'kr',
        'NOK': 'kr',
        'DKK': 'kr',
        'ZAR': 'R',
        'SAR': 'SR',
        'ILS': '₪',
        'TRY': '₺',
    }

    # Sub-unit currencies reported by Yahoo Finance that need conversion
    # to their standard ISO 4217 major unit.
    # Format: { yahoo_code: (iso_code, divisor) }
    SUB_UNIT_CURRENCIES = {
        'GBP': ('GBP', 100),    # GBp (pence) → GBP; Yahoo returns "GBp" which uppercases to "GBP"
        'ILA': ('ILS', 100),    # Israeli Agorot → Israeli Shekel
        'ZAC': ('ZAR', 100),    # South African cents → South African Rand
    }

    @classmethod
    def normalize_yahoo_currency(cls, yahoo_currency: str, price: float) -> tuple:
        """
        Normalize sub-unit currencies from Yahoo Finance to standard ISO codes.

        Yahoo Finance reports some stocks in sub-units (e.g., British pence "GBp"
        instead of pounds "GBP"). This method converts both the currency code
        and the price to the major unit.

        Args:
            yahoo_currency: Currency code as returned by Yahoo Finance (e.g., 'GBp', 'ILA')
            price: Price in the Yahoo-reported currency

        Returns:
            tuple: (normalized_currency_code, normalized_price)
        """
        if not yahoo_currency:
            return yahoo_currency, price

        # Yahoo returns "GBp" for pence — detect before uppercasing
        raw = yahoo_currency.strip()
        is_pence = (raw == 'GBp' or raw == 'GBX')

        code = raw.upper()

        if is_pence:
            return 'GBP', price / 100.0 if price else price

        if code in cls.SUB_UNIT_CURRENCIES:
            iso_code, divisor = cls.SUB_UNIT_CURRENCIES[code]
            return iso_code, price / divisor if price else price

        return code, price

    # Ticker exchange suffixes where yf.download() returns prices in sub-units.
    # These exchanges conventionally quote prices in minor currency units.
    SUBUNIT_TICKER_SUFFIXES = {
        '.L': 100,      # LSE: prices in pence, need /100 for GBP
    }

    @classmethod
    def normalize_price_for_ticker(cls, ticker_symbol: str, price: float) -> float:
        """
        Normalize a price from yf.download() that may be in sub-units.

        yf.download() returns raw exchange prices without currency metadata.
        For exchanges like the LSE (.L suffix), prices are in pence rather
        than pounds. This method converts to the major currency unit.

        Args:
            ticker_symbol: Stock ticker (e.g., 'WISE.L', 'AAPL')
            price: Raw price from yf.download()

        Returns:
            float: Price normalized to major currency unit
        """
        if not ticker_symbol or price is None:
            return price

        ticker = ticker_symbol.upper().strip()
        for suffix, divisor in cls.SUBUNIT_TICKER_SUFFIXES.items():
            if ticker.endswith(suffix):
                return price / divisor

        return price

    @classmethod
    def detect_currency_from_ticker(cls, ticker_symbol: str) -> str:
        """
        Detect currency based on ticker exchange suffix.

        Args:
            ticker_symbol: Stock ticker (e.g., 'AAPL', 'SAP.DE', 'BP.L')

        Returns:
            str: ISO 4217 currency code (e.g., 'USD', 'EUR', 'GBP')
        """
        if not ticker_symbol:
            return 'USD'

        ticker = ticker_symbol.upper().strip()

        # Check for exchange suffix (check non-empty suffixes first)
        for suffix, currency in cls.TICKER_CURRENCY_MAP.items():
            if suffix != '' and ticker.endswith(suffix):
                return currency

        # Check if US stock (no suffix or share class like BRK.B)
        if '.' not in ticker or (ticker.count('.') == 1 and len(ticker.split('.')[-1]) == 1):
            return 'USD'

        # Default to USD if no match
        return 'USD'

    @classmethod
    def get_currency_symbol(cls, currency: str) -> str:
        """Get currency symbol for display (e.g., '$', '€', '£')"""
        return cls.CURRENCY_SYMBOLS.get(currency.upper(), currency)

    @classmethod
    def get_currency_name(cls, currency: str) -> str:
        """Get full currency name (e.g., 'US Dollar', 'Euro')"""
        return cls.CURRENCY_NAMES.get(currency.upper(), currency)

    @classmethod
    def get_exchange_rate(cls, from_currency: str, to_currency: str, rate_date: date = None) -> Decimal:
        """
        Get exchange rate for a currency pair on a specific date.
        Uses cached rates when available, fetches from API if needed.

        Args:
            from_currency: Source currency code (e.g., 'EUR')
            to_currency: Target currency code (e.g., 'USD')
            rate_date: Date for exchange rate (default: today)

        Returns:
            Decimal: Exchange rate (e.g., 1.08 for EUR to USD)
        """
        # Same currency = 1.0 rate
        if from_currency == to_currency:
            return Decimal('1.0')

        if rate_date is None:
            rate_date = now_utc().date()

        # Check cache first
        cached_rate = ExchangeRate.query.filter_by(
            from_currency=from_currency.upper(),
            to_currency=to_currency.upper(),
            date=rate_date
        ).first()

        if cached_rate:
            return cached_rate.rate

        # Fetch from API
        try:
            rate = cls.fetch_exchange_rate_from_api(from_currency, to_currency)

            # Cache the rate
            cls.cache_exchange_rate(from_currency, to_currency, rate, rate_date)

            return rate

        except Exception as e:
            print(f"Error fetching exchange rate {from_currency}/{to_currency}: {str(e)}")
            # If today's rate fails, try yesterday's cached rate as fallback
            yesterday = rate_date - timedelta(days=1)
            fallback_rate = ExchangeRate.query.filter_by(
                from_currency=from_currency.upper(),
                to_currency=to_currency.upper(),
                date=yesterday
            ).first()

            if fallback_rate:
                return fallback_rate.rate

            # Last resort: return 1.0 (will cause issues but prevents crashes)
            print(f"WARNING: Using rate 1.0 as fallback for {from_currency}/{to_currency}")
            return Decimal('1.0')

    @classmethod
    def fetch_exchange_rate_from_api(cls, from_currency: str, to_currency: str) -> Decimal:
        """
        Fetch current exchange rate from Yahoo Finance API.

        Args:
            from_currency: Source currency (e.g., 'EUR')
            to_currency: Target currency (e.g., 'USD')

        Returns:
            Decimal: Exchange rate

        Raises:
            Exception: If API call fails
        """
        # Lazy import to avoid circular dependency (YahooFinanceProvider imports CurrencyService)
        from app.services.financial_data.providers.yahoo_finance import YahooFinanceProvider

        try:
            provider = YahooFinanceProvider()
            rate = provider.get_exchange_rate(from_currency, to_currency)

            if rate is None:
                fx_ticker = f"{from_currency.upper()}{to_currency.upper()}=X"
                raise ValueError(f"No exchange rate data available for {fx_ticker}")

            return rate

        except Exception as e:
            raise Exception(f"Failed to fetch exchange rate for {from_currency}/{to_currency}: {str(e)}")

    @classmethod
    def cache_exchange_rate(cls, from_currency: str, to_currency: str, rate: Decimal, rate_date: date):
        """
        Cache exchange rate in database to minimize API calls.

        Args:
            from_currency: Source currency
            to_currency: Target currency
            rate: Exchange rate
            rate_date: Date of the rate
        """
        try:
            # Check if already exists
            existing = ExchangeRate.query.filter_by(
                from_currency=from_currency.upper(),
                to_currency=to_currency.upper(),
                date=rate_date
            ).first()

            if existing:
                # Update existing rate
                existing.rate = rate
                existing.fetched_at = now_utc()
                existing.source = 'yahoo'
            else:
                # Create new cache entry
                new_rate = ExchangeRate(
                    from_currency=from_currency.upper(),
                    to_currency=to_currency.upper(),
                    rate=rate,
                    date=rate_date,
                    source='yahoo',
                    fetched_at=now_utc()
                )
                db.session.add(new_rate)

            db.session.commit()

        except Exception as e:
            print(f"Error caching exchange rate: {str(e)}")
            db.session.rollback()

    @classmethod
    def convert_amount(cls, amount: Decimal, from_currency: str, to_currency: str, rate_date: date = None) -> Decimal:
        """
        Convert amount from one currency to another.

        Args:
            amount: Amount in source currency
            from_currency: Source currency code
            to_currency: Target currency code
            rate_date: Date for exchange rate (default: today)

        Returns:
            Decimal: Converted amount
        """
        if amount is None:
            return Decimal('0.00')

        rate = cls.get_exchange_rate(from_currency, to_currency, rate_date)
        return amount * rate

    @classmethod
    def format_currency(cls, amount: Decimal, currency: str, show_symbol: bool = True) -> str:
        """
        Format amount with currency symbol.

        Args:
            amount: Amount to format
            currency: Currency code
            show_symbol: Whether to include currency symbol

        Returns:
            str: Formatted string (e.g., '$100.00', '€85.50')
        """
        if amount is None:
            return 'N/A'

        symbol = cls.get_currency_symbol(currency) if show_symbol else ''

        # Format with 2 decimal places
        formatted_amount = f"{float(amount):,.2f}"

        if show_symbol:
            # Some symbols go before (USD, GBP), some after (EUR in some locales)
            if currency in ['USD', 'GBP', 'CAD', 'AUD', 'HKD']:
                return f"{symbol}{formatted_amount}"
            else:
                return f"{formatted_amount}{symbol}"

        return formatted_amount

    @classmethod
    def format_with_base(cls, amount_original: Decimal, currency_original: str,
                        amount_base: Decimal, currency_base: str) -> str:
        """
        Format amount showing both original and base currency.

        Args:
            amount_original: Amount in original currency
            currency_original: Original currency code
            amount_base: Amount in base currency
            currency_base: Base currency code

        Returns:
            str: Formatted string (e.g., '€65.00 (~$70.20)')
        """
        original_str = cls.format_currency(amount_original, currency_original)

        if currency_original == currency_base:
            return original_str

        base_str = cls.format_currency(amount_base, currency_base)
        return f"{original_str} (~{base_str})"

    @classmethod
    def get_supported_currencies(cls) -> list:
        """
        Get list of all supported currencies.

        Returns:
            list: List of dicts with currency info
        """
        currencies = []
        seen = set()

        for currency in cls.TICKER_CURRENCY_MAP.values():
            if currency not in seen:
                currencies.append({
                    'code': currency,
                    'name': cls.get_currency_name(currency),
                    'symbol': cls.get_currency_symbol(currency)
                })
                seen.add(currency)

        # Sort by code
        return sorted(currencies, key=lambda x: x['code'])
