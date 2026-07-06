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

# app/services/price_service.py

import logging
from datetime import timedelta
from decimal import Decimal
from app import db
from app.models import PortfolioPosition
from app.models.user import User
from app.services.currency_service import CurrencyService
from app.utils.time_utils import now_utc, ensure_timezone_aware

logger = logging.getLogger(__name__)

# Lazy singleton for FinancialDataService (avoids circular imports)
_financial_service = None

def _get_financial_service():
    global _financial_service
    if _financial_service is None:
        from app.services.financial_data import FinancialDataService
        _financial_service = FinancialDataService()
    return _financial_service


class PriceService:
    """
    Service for fetching and updating stock prices.
    Routes all Yahoo Finance calls through FinancialDataService.
    Implements 1-hour caching to minimize API calls.
    Supports multi-currency with automatic currency detection.
    """

    @staticmethod
    def get_current_price(ticker_symbol):
        """
        Fetch current price for a single ticker.

        Args:
            ticker_symbol: Stock ticker (e.g., 'AAPL', 'MSFT')

        Returns:
            float: Current price

        Raises:
            ValueError: If ticker not found
        """
        service = _get_financial_service()
        price = service.get_current_price(ticker_symbol)
        if price is None:
            raise ValueError(f"No price data available for {ticker_symbol}")
        return price

    @staticmethod
    def get_current_price_with_currency(ticker_symbol):
        """
        Fetch current price AND currency for a ticker.

        Args:
            ticker_symbol: Stock ticker (e.g., 'AAPL', 'SAP.DE', 'BP.L')

        Returns:
            dict: {'price': float, 'currency': str}

        Raises:
            ValueError: If ticker not found
        """
        service = _get_financial_service()
        result = service.get_current_price_with_currency(ticker_symbol)
        if result is None:
            raise ValueError(f"No price data available for {ticker_symbol}")
        return result

    @staticmethod
    def should_update_price(position):
        """
        Check if position price needs updating based on 1-hour cache policy.

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
        return time_since_update > timedelta(hours=1)

    @staticmethod
    def update_position_price(position, force=False):
        """
        Update single position with current price.
        Converts price to user's base currency for consistent P&L calculation.
        Respects 1-hour cache unless force=True.

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

            # Calculate unrealized gains/losses in base currency
            # Note: total_cost is already in user's base currency (FIFO uses _base prices)
            total_cost = position.total_cost or Decimal('0.00')
            if total_cost > 0:
                position.unrealized_gain_loss = position.current_value - total_cost
                position.unrealized_gain_loss_pct = (
                    (position.unrealized_gain_loss / total_cost) * 100
                )
            else:
                position.unrealized_gain_loss = Decimal('0.00')
                position.unrealized_gain_loss_pct = Decimal('0.00')

            position.last_price_update = now_utc()
            db.session.commit()

            return True

        except ValueError as e:
            # Ticker not found or no price data
            logger.warning("Price update failed for %s: %s", position.company.ticker_symbol, e)
            return False

        except Exception as e:
            # Other errors (network, API rate limit, etc.)
            logger.error("Unexpected error updating price for %s: %s", position.company.ticker_symbol, e)
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
        Fetch prices for multiple tickers via FinancialDataService.

        Uses the same API path as individual price fetching for consistency.

        Args:
            ticker_symbols: List of ticker symbols

        Returns:
            dict: {ticker: price} mapping, None for failed tickers
        """
        if not ticker_symbols:
            return {}

        service = _get_financial_service()
        batch_results = service.get_batch_current_prices(ticker_symbols)

        # Convert to {ticker: price} format expected by update_all_positions_batch
        results = {}
        for ticker, data in batch_results.items():
            if data is not None:
                results[ticker] = data['price']
            else:
                results[ticker] = None

        fetched = sum(1 for v in results.values() if v is not None)
        logger.info("Batch prices: %d/%d fetched", fetched, len(ticker_symbols))
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

        # Fetch prices with currency in batch (same API as individual calls)
        service = _get_financial_service()
        batch_data = service.get_batch_current_prices(ticker_symbols)

        # Update each position
        for position in positions_to_update:
            ticker = position.company.ticker_symbol
            price_data = batch_data.get(ticker)

            if price_data is None:
                results['failed'] += 1
                results['errors'].append(ticker)
                continue

            try:
                native_price = Decimal(str(price_data['price']))
                stock_currency = price_data['currency']
                position.current_price = native_price

                # Auto-set company reporting_currency if not yet set
                company = position.company
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

                # Calculate unrealized gains/losses in base currency
                total_cost = position.total_cost or Decimal('0.00')
                if total_cost > 0:
                    position.unrealized_gain_loss = position.current_value - total_cost
                    position.unrealized_gain_loss_pct = (
                        (position.unrealized_gain_loss / total_cost) * 100
                    )
                else:
                    position.unrealized_gain_loss = Decimal('0.00')
                    position.unrealized_gain_loss_pct = Decimal('0.00')

                position.last_price_update = now_utc()
                results['updated'] += 1

            except Exception as e:
                logger.error("Error updating position for %s: %s", ticker, e)
                results['failed'] += 1
                results['errors'].append(ticker)

        # Commit all updates at once
        try:
            db.session.commit()
        except Exception as e:
            logger.error("Error committing price updates: %s", e)
            db.session.rollback()

        return results
