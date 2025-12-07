"""
Ticker Symbol Validator and Parser
Handles multiple ticker formats from different financial data providers
"""

import re
from typing import Tuple, Optional, Dict


class TickerValidator:
    """
    Validates and normalizes ticker symbols from various formats
    (Google Finance, Yahoo Finance, Bloomberg, etc.)
    """

    # Exchange code mapping: Google Finance prefix → Yahoo Finance suffix
    EXCHANGE_MAP = {
        # US Markets (no suffix in Yahoo)
        'NYSE': '',
        'NASDAQ': '',
        'NYSEAMERICAN': '',
        'NYSEARCA': '',  # ETFs
        'BATS': '',
        'OTC': '',
        'OTCMKTS': '',

        # International Markets
        'FRA': '.F',       # Frankfurt → Germany (Frankfurt)
        'ETR': '.DE',      # XETRA → Germany (XETRA)
        'BER': '.BE',      # Berlin → Germany
        'MUN': '.MU',      # Munich → Germany
        'STU': '.SG',      # Stuttgart → Germany
        'DUS': '.DU',      # Dusseldorf → Germany
        'HAM': '.HM',      # Hamburg → Germany

        'LON': '.L',       # London
        'LSE': '.L',       # London Stock Exchange

        'EPA': '.PA',      # Euronext Paris
        'PAR': '.PA',      # Paris

        'TYO': '.T',       # Tokyo
        'JPX': '.T',       # Japan Exchange

        'TSE': '.TO',      # Toronto
        'CVE': '.V',       # Canadian Venture Exchange

        'NSE': '.NS',      # National Stock Exchange of India
        'BOM': '.BO',      # Bombay Stock Exchange

        'HKG': '.HK',      # Hong Kong
        'HKEX': '.HK',     # Hong Kong Exchange

        'SHE': '.SZ',      # Shenzhen
        'SHA': '.SS',      # Shanghai

        'KRX': '.KS',      # Korea Exchange
        'KSE': '.KS',      # Korea Stock Exchange

        'ASX': '.AX',      # Australian Securities Exchange

        'SWX': '.SW',      # Swiss Exchange
        'VTX': '.SW',      # SIX Swiss Exchange

        'AMS': '.AS',      # Amsterdam
        'BRU': '.BR',      # Brussels
        'EBR': '.BR',      # Euronext Brussels
        'CPH': '.CO',      # Copenhagen
        'HEL': '.HE',      # Helsinki
        'STO': '.ST',      # Stockholm
        'OSL': '.OL',      # Oslo

        'BME': '.MC',      # Madrid
        'MCE': '.MC',      # Bolsa de Madrid
        'BIT': '.MI',      # Milan

        'JSE': '.JO',      # Johannesburg
        'TAE': '.TA',      # Tel Aviv
        'IST': '.IS',      # Istanbul
        'SAU': '.SA',      # Saudi Arabia
    }

    # Reverse mapping for display purposes
    EXCHANGE_NAMES = {
        '': 'United States',
        '.DE': 'Germany (XETRA)',
        '.F': 'Germany (Frankfurt)',
        '.BE': 'Germany (Berlin)',
        '.MU': 'Germany (Munich)',
        '.SG': 'Germany (Stuttgart)',
        '.DU': 'Germany (Dusseldorf)',
        '.HM': 'Germany (Hamburg)',
        '.HA': 'Germany (Hanover)',
        '.L': 'United Kingdom (LSE)',
        '.PA': 'France (Euronext Paris)',
        '.T': 'Japan (Tokyo)',
        '.TO': 'Canada (Toronto)',
        '.V': 'Canada (Venture)',
        '.NS': 'India (NSE)',
        '.BO': 'India (BSE)',
        '.HK': 'Hong Kong',
        '.SZ': 'China (Shenzhen)',
        '.SS': 'China (Shanghai)',
        '.KS': 'South Korea',
        '.AX': 'Australia',
        '.SW': 'Switzerland',
        '.AS': 'Netherlands',
        '.BR': 'Belgium',
        '.CO': 'Denmark',
        '.HE': 'Finland',
        '.ST': 'Sweden',
        '.OL': 'Norway',
        '.MC': 'Spain',
        '.MI': 'Italy',
        '.JO': 'South Africa',
        '.TA': 'Israel',
        '.IS': 'Turkey',
        '.SA': 'Saudi Arabia',
        '.NZ': 'New Zealand',
        '.TW': 'Taiwan',
        '.VI': 'Austria (Vienna)',
        '.PR': 'Czech Republic (Prague)',
        '.WA': 'Poland (Warsaw)',
        '.BD': 'Hungary (Budapest)',
        '.IC': 'Iceland',
        '.IR': 'Ireland',
        '.LS': 'Portugal (Lisbon)',
        '.AT': 'Greece (Athens)',
        '.RG': 'Latvia (Riga)',
        '.TL': 'Estonia (Tallinn)',
        '.VS': 'Lithuania (Vilnius)',
    }

    @classmethod
    def parse_and_validate(cls, ticker_input: str) -> Dict:
        """
        Parse and validate a ticker symbol from any format

        Args:
            ticker_input: Raw ticker string (e.g., "NYSE:AAPL", "SAP.DE", "FRA:1TY")

        Returns:
            Dict with:
                - is_valid: bool
                - normalized_ticker: str (Yahoo Finance format)
                - display_ticker: str (for showing to user)
                - exchange_code: str (suffix like .DE)
                - exchange_name: str (human readable)
                - original_format: str (google/yahoo/plain)
                - errors: list of error messages
                - warnings: list of warning messages
        """
        result = {
            'is_valid': False,
            'normalized_ticker': None,
            'display_ticker': None,
            'exchange_code': '',
            'exchange_name': 'United States',
            'original_format': 'unknown',
            'errors': [],
            'warnings': []
        }

        if not ticker_input:
            result['errors'].append('Ticker symbol is required')
            return result

        # Clean and uppercase
        ticker = ticker_input.strip().upper()

        if len(ticker) > 20:
            result['errors'].append('Ticker too long (max 20 characters)')
            return result

        # Try to parse the ticker
        parsed = cls._parse_ticker_format(ticker)

        if not parsed['success']:
            result['errors'].append(parsed['error'])
            return result

        result['original_format'] = parsed['format']
        result['normalized_ticker'] = parsed['normalized']
        result['display_ticker'] = parsed['display']
        result['exchange_code'] = parsed['exchange_suffix']
        result['exchange_name'] = cls.EXCHANGE_NAMES.get(
            parsed['exchange_suffix'],
            'Unknown Exchange'
        )

        # Validate the normalized ticker format
        validation = cls._validate_normalized_ticker(parsed['normalized'])

        if not validation['is_valid']:
            result['errors'].extend(validation['errors'])
            return result

        result['is_valid'] = True
        result['warnings'] = validation['warnings']

        return result

    @classmethod
    def _parse_ticker_format(cls, ticker: str) -> Dict:
        """
        Parse ticker from various formats and normalize to Yahoo Finance format
        """
        # Format 1: Google Finance format (PREFIX:TICKER)
        # Examples: NYSE:AAPL, FRA:SAP, NSE:RELIANCE
        google_pattern = r'^([A-Z]{2,15}):([A-Z0-9.]{1,10})$'
        match = re.match(google_pattern, ticker)

        if match:
            exchange_prefix = match.group(1)
            symbol = match.group(2)

            # Map exchange prefix to Yahoo suffix
            exchange_suffix = cls.EXCHANGE_MAP.get(exchange_prefix)

            if exchange_suffix is None:
                return {
                    'success': False,
                    'error': f'Unknown exchange: {exchange_prefix}. Please use Yahoo format (e.g., SAP.DE) or contact support.'
                }

            # Handle share classes: Convert dots to hyphens for US stocks
            if exchange_suffix == '' and '.' in symbol:
                # US stock with share class (e.g., BRK.B → BRK-B)
                symbol = symbol.replace('.', '-')

            normalized = symbol + exchange_suffix
            display = f"{exchange_prefix}:{symbol}"

            return {
                'success': True,
                'format': 'google',
                'normalized': normalized,
                'display': display,
                'exchange_suffix': exchange_suffix
            }

        # Format 2: Check for US share class FIRST (before general Yahoo pattern)
        # Examples: BRK.B, BF.A (single letter after dot = share class, not exchange)
        if '.' in ticker and ':' not in ticker:
            if re.match(r'^[A-Z]{1,5}\.[A-Z]$', ticker):
                normalized = ticker.replace('.', '-')
                return {
                    'success': True,
                    'format': 'yahoo',
                    'normalized': normalized,
                    'display': ticker,
                    'exchange_suffix': ''
                }

        # Format 3: Yahoo Finance format (TICKER.SUFFIX)
        # Examples: AAPL, SAP.DE, RELIANCE.NS, BRK-B
        yahoo_pattern = r'^([A-Z0-9-]{1,10})(\.[A-Z]{1,3})?$'
        match = re.match(yahoo_pattern, ticker)

        if match:
            symbol = match.group(1)
            exchange_suffix = match.group(2) or ''

            # Validate exchange suffix exists in our map
            if exchange_suffix and exchange_suffix not in cls.EXCHANGE_NAMES:
                return {
                    'success': False,
                    'error': f'Unknown exchange suffix: {exchange_suffix}'
                }

            normalized = symbol + exchange_suffix
            display = ticker

            return {
                'success': True,
                'format': 'yahoo',
                'normalized': normalized,
                'display': display,
                'exchange_suffix': exchange_suffix
            }

        # If we reach here, the format is invalid
        return {
            'success': False,
            'error': 'Invalid ticker format. Use TICKER (e.g., AAPL), TICKER.XX (e.g., SAP.DE), or EXCHANGE:TICKER (e.g., FRA:SAP)'
        }

    @classmethod
    def _validate_normalized_ticker(cls, ticker: str) -> Dict:
        """
        Validate a normalized ticker (Yahoo Finance format)
        """
        result = {
            'is_valid': True,
            'errors': [],
            'warnings': []
        }

        # Split ticker and exchange
        if '.' in ticker:
            parts = ticker.split('.')
            if len(parts) != 2:
                result['is_valid'] = False
                result['errors'].append('Invalid format: multiple dots found')
                return result

            symbol, exchange = parts
        else:
            symbol = ticker
            exchange = ''

        # Validate symbol part (base ticker)
        # Allow: Letters, numbers, hyphens (for share classes)
        # Length: 1-10 characters
        if not re.match(r'^[A-Z0-9-]{1,10}$', symbol):
            result['is_valid'] = False
            result['errors'].append('Ticker symbol must be 1-10 alphanumeric characters or hyphens')
            return result

        # Check for invalid patterns
        if symbol.startswith('-') or symbol.endswith('-'):
            result['is_valid'] = False
            result['errors'].append('Ticker cannot start or end with a hyphen')
            return result

        if '--' in symbol:
            result['is_valid'] = False
            result['errors'].append('Ticker cannot contain consecutive hyphens')
            return result

        # Validate exchange suffix if present
        if exchange:
            if not re.match(r'^[A-Z]{1,3}$', exchange):
                result['is_valid'] = False
                result['errors'].append('Exchange suffix must be 1-3 uppercase letters')
                return result

            full_suffix = '.' + exchange
            if full_suffix not in cls.EXCHANGE_NAMES:
                result['warnings'].append(f'Unknown exchange suffix: {full_suffix}')

        # Warnings for unusual patterns
        if len(symbol) == 1:
            result['warnings'].append('Single-character tickers are rare')

        if len(symbol) > 5 and not exchange:
            result['warnings'].append('Long US ticker symbols are uncommon')

        if re.match(r'^[0-9]', symbol):
            result['warnings'].append('Ticker starts with a number - common for some international exchanges')

        if '-' in symbol and exchange:
            result['warnings'].append('Share class indicators (hyphen) are typically only used for US stocks')

        return result

    @classmethod
    def get_base_ticker(cls, ticker: str) -> str:
        """
        Extract base ticker without exchange suffix or share class
        Examples:
            - AAPL → AAPL
            - SAP.DE → SAP
            - BRK-B → BRK
            - VOW3.DE → VOW3
        """
        # Remove exchange suffix
        if '.' in ticker:
            ticker = ticker.split('.')[0]

        # Remove share class (hyphen)
        if '-' in ticker:
            ticker = ticker.split('-')[0]

        return ticker

    @classmethod
    def format_for_display(cls, ticker: str, include_exchange_name: bool = True) -> str:
        """
        Format ticker for display to user
        """
        result = cls.parse_and_validate(ticker)

        if not result['is_valid']:
            return ticker

        if include_exchange_name and result['exchange_code']:
            return f"{result['normalized_ticker']} ({result['exchange_name']})"

        return result['normalized_ticker']

    @staticmethod
    def validate_ticker(ticker_symbol: str) -> Dict:
        """
        Validate ticker symbol against Yahoo Finance API

        Args:
            ticker_symbol: Stock ticker to validate

        Returns:
            Dict with validation results including price data if valid
        """
        import yfinance as yf

        result = {
            'valid': False,
            'ticker': ticker_symbol.upper(),
            'error': None,
            'company_name': None,
            'current_price': None,
            'exchange': None
        }

        if not ticker_symbol or not ticker_symbol.strip():
            result['error'] = 'Ticker symbol is required'
            return result

        ticker = ticker_symbol.strip().upper()
        result['ticker'] = ticker

        # Basic format validation
        if len(ticker) > 20:
            result['error'] = 'Ticker too long (max 20 characters)'
            return result

        try:
            # Fetch data from Yahoo Finance
            ticker_obj = yf.Ticker(ticker)
            info = ticker_obj.info

            # Check if ticker exists (Yahoo returns minimal info for invalid tickers)
            if not info or 'symbol' not in info:
                result['error'] = f'Ticker "{ticker}" not found on Yahoo Finance'
                return result

            # Get company name
            company_name = (
                info.get('longName') or
                info.get('shortName') or
                info.get('symbol')
            )

            # Get current price
            current_price = (
                info.get('currentPrice') or
                info.get('regularMarketPrice') or
                info.get('previousClose')
            )

            # Get exchange
            exchange = info.get('exchange') or info.get('market')

            # If we have at least a company name, consider it valid
            if company_name:
                result['valid'] = True
                result['company_name'] = company_name
                result['current_price'] = float(current_price) if current_price else None
                result['exchange'] = exchange
            else:
                result['error'] = f'Unable to retrieve information for "{ticker}"'

        except Exception as e:
            error_msg = str(e)
            if '404' in error_msg or 'not found' in error_msg.lower():
                result['error'] = f'Ticker "{ticker}" not found'
            else:
                result['error'] = f'Error validating ticker: {error_msg}'

        return result


# Convenience functions for quick validation
def validate_ticker(ticker: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Quick validation function

    Returns:
        (is_valid, normalized_ticker, error_message)
    """
    result = TickerValidator.parse_and_validate(ticker)

    if result['is_valid']:
        return True, result['normalized_ticker'], None
    else:
        error_msg = '; '.join(result['errors'])
        return False, None, error_msg


def normalize_ticker(ticker: str) -> Optional[str]:
    """
    Normalize ticker to Yahoo Finance format

    Returns:
        Normalized ticker or None if invalid
    """
    result = TickerValidator.parse_and_validate(ticker)
    return result['normalized_ticker'] if result['is_valid'] else None
