# app/services/price_service.py

from datetime import timedelta
from decimal import Decimal
import yfinance as yf
from app import db
from app.models import PortfolioPosition
from app.models.user import User
from app.services.currency_service import CurrencyService
from app.utils.time_utils import now_utc, ensure_timezone_aware

class PriceService:
    """
    Service for fetching and updating stock prices from Yahoo Finance.
    Implements 15-minute caching to minimize API calls.
    Supports multi-currency with automatic currency detection.
    """

    @staticmethod
    def get_current_price(ticker_symbol):
        """
        Fetch current price for a single ticker from Yahoo Finance.

        Args:
            ticker_symbol: Stock ticker (e.g., 'AAPL', 'MSFT')

        Returns:
            float: Current price, or None if error

        Raises:
            ValueError: If ticker not found
            Exception: For other API errors
        """
        try:
            ticker = yf.Ticker(ticker_symbol)
            info = ticker.info

            # Try multiple price fields (Yahoo Finance API can be inconsistent)
            price = (
                info.get('currentPrice') or
                info.get('regularMarketPrice') or
                info.get('previousClose')
            )

            if price is None:
                raise ValueError(f"No price data available for {ticker_symbol}")

            return float(price)

        except Exception as e:
            print(f"Error fetching price for {ticker_symbol}: {str(e)}")
            raise

    @staticmethod
    def get_current_price_with_currency(ticker_symbol):
        """
        Fetch current price AND currency for a ticker from Yahoo Finance.

        Args:
            ticker_symbol: Stock ticker (e.g., 'AAPL', 'SAP.DE', 'BP.L')

        Returns:
            dict: {
                'price': float,
                'currency': str (ISO code like 'USD', 'EUR', 'GBP')
            }

        Raises:
            ValueError: If ticker not found
            Exception: For other API errors
        """
        try:
            ticker = yf.Ticker(ticker_symbol)
            info = ticker.info

            # Get price
            price = (
                info.get('currentPrice') or
                info.get('regularMarketPrice') or
                info.get('previousClose')
            )

            if price is None:
                raise ValueError(f"No price data available for {ticker_symbol}")

            # Get currency from Yahoo Finance
            # Yahoo provides currency in the 'currency' field
            yahoo_currency = info.get('currency', '').upper()

            # If Yahoo didn't provide currency, detect from ticker
            if not yahoo_currency or yahoo_currency == 'NONE':
                currency = CurrencyService.detect_currency_from_ticker(ticker_symbol)
            else:
                currency = yahoo_currency

            return {
                'price': float(price),
                'currency': currency
            }

        except Exception as e:
            print(f"Error fetching price/currency for {ticker_symbol}: {str(e)}")
            raise

    @staticmethod
    def should_update_price(position):
        """
        Check if position price needs updating based on 15-minute cache policy.

        Args:
            position: PortfolioPosition object

        Returns:
            bool: True if price should be updated
        """
        if not position.last_price_update:
            return True

        # Ensure timezone-aware comparison
        last_update_aware = ensure_timezone_aware(position.last_price_update)
        time_since_update = now_utc() - last_update_aware
        return time_since_update > timedelta(minutes=15)

    @staticmethod
    def update_position_price(position, force=False):
        """
        Update single position with current price from Yahoo Finance.
        Converts price to user's base currency for consistent P&L calculation.
        Respects 15-minute cache unless force=True.

        Args:
            position: PortfolioPosition object
            force: If True, bypass cache and force update

        Returns:
            bool: True if updated successfully, False otherwise
        """
        # Check cache policy
        if not force and not PriceService.should_update_price(position):
            return True  # Already up to date

        try:
            # Fetch current price with currency info
            price_data = PriceService.get_current_price_with_currency(position.company.ticker_symbol)
            native_price = Decimal(str(price_data['price']))
            stock_currency = price_data['currency']

            # Auto-set company reporting_currency if not yet set
            company = position.company
            if not company.reporting_currency:
                company.reporting_currency = stock_currency

            # Store native price (stock's trading currency)
            position.current_price = native_price

            # Convert to user's base currency
            user_base_currency = position.user.base_currency
            if stock_currency != user_base_currency:
                exchange_rate = CurrencyService.get_exchange_rate(
                    from_currency=stock_currency,
                    to_currency=user_base_currency
                )
                current_price_base = native_price * exchange_rate
                position.current_exchange_rate = exchange_rate
            else:
                current_price_base = native_price
                position.current_exchange_rate = Decimal('1.0')

            position.current_price_base = current_price_base
            position.last_exchange_rate_update = now_utc()

            # Calculate values in base currency
            position.current_value = position.total_shares * current_price_base
            position.current_value_base = position.current_value

            # Calculate unrealized gains/losses (both in base currency now)
            if position.total_cost > 0:
                position.unrealized_gain_loss = position.current_value - position.total_cost
                position.unrealized_gain_loss_pct = (
                    (position.unrealized_gain_loss / position.total_cost) * 100
                )
            else:
                position.unrealized_gain_loss = Decimal('0.00')
                position.unrealized_gain_loss_pct = Decimal('0.00')

            position.last_price_update = now_utc()
            db.session.commit()

            return True

        except ValueError as e:
            # Ticker not found or no price data
            print(f"Price update failed for {position.company.ticker_symbol}: {str(e)}")
            return False

        except Exception as e:
            # Other errors (network, API rate limit, etc.)
            print(f"Unexpected error updating price for {position.company.ticker_symbol}: {str(e)}")
            db.session.rollback()
            return False

    @staticmethod
    def update_all_positions(user_id, force=False):
        """
        Update all active positions for a user.
        Only updates positions that need updating based on cache policy (unless force=True).

        Args:
            user_id: User ID
            force: If True, bypass cache and force update all

        Returns:
            dict: {
                'updated': int (number of positions updated),
                'skipped': int (number skipped due to cache),
                'failed': int (number that failed to update),
                'errors': list (ticker symbols that failed)
            }
        """
        positions = PortfolioPosition.query.filter_by(
            user_id=user_id,
            is_active=True
        ).all()

        results = {
            'updated': 0,
            'skipped': 0,
            'failed': 0,
            'errors': []
        }

        for position in positions:
            # Check if update needed
            if not force and not PriceService.should_update_price(position):
                results['skipped'] += 1
                continue

            # Attempt update
            success = PriceService.update_position_price(position, force=True)

            if success:
                results['updated'] += 1
            else:
                results['failed'] += 1
                results['errors'].append(position.company.ticker_symbol)

        return results

    @staticmethod
    def get_portfolio_value(user_id):
        """
        Calculate total portfolio value for a user.
        Updates prices if needed before calculating.

        Args:
            user_id: User ID

        Returns:
            dict: {
                'total_value': Decimal,
                'total_cost': Decimal,
                'total_unrealized_gain_loss': Decimal,
                'total_unrealized_gain_loss_pct': Decimal,
                'positions_count': int
            }
        """
        # Get all active positions
        positions = PortfolioPosition.query.filter_by(
            user_id=user_id,
            is_active=True
        ).all()

        # Update prices if needed
        for position in positions:
            if PriceService.should_update_price(position):
                PriceService.update_position_price(position)

        # Calculate totals
        total_value = Decimal('0.00')
        total_cost = Decimal('0.00')
        total_unrealized_gain_loss = Decimal('0.00')

        for position in positions:
            if position.current_value:
                total_value += position.current_value
            total_cost += position.total_cost
            if position.unrealized_gain_loss:
                total_unrealized_gain_loss += position.unrealized_gain_loss

        # Calculate overall percentage
        total_unrealized_gain_loss_pct = Decimal('0.00')
        if total_cost > 0:
            total_unrealized_gain_loss_pct = (total_unrealized_gain_loss / total_cost) * 100

        # Include cash balance in total portfolio value
        user = User.query.get(user_id)
        cash_balance = Decimal(str(user.cash_balance)) if user and user.cash_balance else Decimal('0.00')

        return {
            'total_value': total_value + cash_balance,
            'total_cost': total_cost,
            'total_unrealized_gain_loss': total_unrealized_gain_loss,
            'total_unrealized_gain_loss_pct': total_unrealized_gain_loss_pct,
            'positions_count': len(positions),
            'cash_balance': cash_balance,
            'invested_value': total_value,
        }

    @staticmethod
    def get_batch_prices(ticker_symbols):
        """
        Fetch prices for multiple tickers in a single batch.
        More efficient than individual calls for bulk updates.

        Args:
            ticker_symbols: List of ticker symbols

        Returns:
            dict: {ticker: price} mapping, None for failed tickers
        """
        if not ticker_symbols:
            return {}

        results = {}

        try:
            # Fetch data for multiple tickers at once
            tickers = yf.Tickers(' '.join(ticker_symbols))

            for symbol in ticker_symbols:
                try:
                    ticker = tickers.tickers[symbol]
                    info = ticker.info

                    price = (
                        info.get('currentPrice') or
                        info.get('regularMarketPrice') or
                        info.get('previousClose')
                    )

                    results[symbol] = float(price) if price else None

                except Exception as e:
                    print(f"Error fetching price for {symbol}: {str(e)}")
                    results[symbol] = None

        except Exception as e:
            print(f"Error in batch price fetch: {str(e)}")
            # Fallback to individual fetches
            for symbol in ticker_symbols:
                try:
                    results[symbol] = PriceService.get_current_price(symbol)
                except:
                    results[symbol] = None

        return results

    @staticmethod
    def update_all_positions_batch(user_id, force=False):
        """
        Update all positions using batch API call for better performance.

        Args:
            user_id: User ID
            force: If True, bypass cache and force update all

        Returns:
            dict: Update results (same format as update_all_positions)
        """
        positions = PortfolioPosition.query.filter_by(
            user_id=user_id,
            is_active=True
        ).all()

        # Filter positions that need updates
        positions_to_update = []
        if force:
            positions_to_update = positions
        else:
            positions_to_update = [
                p for p in positions
                if PriceService.should_update_price(p)
            ]

        results = {
            'updated': 0,
            'skipped': len(positions) - len(positions_to_update),
            'failed': 0,
            'errors': []
        }

        if not positions_to_update:
            return results

        # Get all tickers
        ticker_symbols = [p.company.ticker_symbol for p in positions_to_update]

        # Fetch prices in batch
        prices = PriceService.get_batch_prices(ticker_symbols)

        # Update each position
        for position in positions_to_update:
            ticker = position.company.ticker_symbol
            price = prices.get(ticker)

            if price is None:
                results['failed'] += 1
                results['errors'].append(ticker)
                continue

            try:
                native_price = Decimal(str(price))
                position.current_price = native_price

                # Detect stock currency and convert to base
                company = position.company
                stock_currency = company.reporting_currency or CurrencyService.detect_currency_from_ticker(ticker)
                if not company.reporting_currency:
                    company.reporting_currency = stock_currency

                user_base_currency = position.user.base_currency
                if stock_currency != user_base_currency:
                    exchange_rate = CurrencyService.get_exchange_rate(
                        from_currency=stock_currency,
                        to_currency=user_base_currency
                    )
                    current_price_base = native_price * exchange_rate
                    position.current_exchange_rate = exchange_rate
                else:
                    current_price_base = native_price
                    position.current_exchange_rate = Decimal('1.0')

                position.current_price_base = current_price_base
                position.last_exchange_rate_update = now_utc()

                # Values in base currency
                position.current_value = position.total_shares * current_price_base
                position.current_value_base = position.current_value

                # Calculate unrealized gains/losses (both in base currency)
                if position.total_cost > 0:
                    position.unrealized_gain_loss = position.current_value - position.total_cost
                    position.unrealized_gain_loss_pct = (
                        (position.unrealized_gain_loss / position.total_cost) * 100
                    )
                else:
                    position.unrealized_gain_loss = Decimal('0.00')
                    position.unrealized_gain_loss_pct = Decimal('0.00')

                position.last_price_update = now_utc()
                results['updated'] += 1

            except Exception as e:
                print(f"Error updating position for {ticker}: {str(e)}")
                results['failed'] += 1
                results['errors'].append(ticker)

        # Commit all updates at once
        try:
            db.session.commit()
        except Exception as e:
            print(f"Error committing price updates: {str(e)}")
            db.session.rollback()

        return results
