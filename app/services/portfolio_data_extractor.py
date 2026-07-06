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
Portfolio Data Extraction Service

Extracts portfolio data in two modes:
1. RAW MODE: Pure transaction data for unbiased LLM analysis
2. STRUCTURED MODE: Pre-calculated metrics for traditional analytics

Usage:
    extractor = PortfolioDataExtractor(user_id=1)

    # Raw transactions (unbiased for LLM)
    raw_data = extractor.extract_transactions(
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        exclude_positions_opened_before=True
    )

    # Structured metrics (for dashboards)
    full_data = extractor.extract_all()
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import date, timedelta
from app.utils.time_utils import now_utc

from app.models.portfolio import Transaction, PortfolioPosition
from app.models.company import Company
from app.utils.financial_utils import calculate_cagr, calculate_total_return

logger = logging.getLogger(__name__)


class PortfolioDataExtractor:
    """
    Extracts structured data from portfolio for analysis.

    Provides both raw transaction data and pre-calculated metrics.
    """

    def __init__(self, user_id: int):
        """
        Initialize extractor for a user.

        Args:
            user_id: User ID to extract data for
        """
        self.user_id = user_id

    # ================================================================
    # RAW TRANSACTION EXTRACTION (Unbiased for LLM)
    # ================================================================

    def extract_transactions(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        exclude_positions_opened_before: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Extract raw transaction data for a time period.

        Returns pure transaction data without pre-calculated metrics,
        allowing LLM to discover patterns without bias.

        Args:
            start_date: Filter transactions >= this date (None = all history)
            end_date: Filter transactions <= this date (None = today)
            exclude_positions_opened_before: If True, exclude transactions for
                positions where initial BUY was before start_date.
                Motivation: Analyze trading skills within a specific timeframe.

        Returns:
            List of transaction dicts with raw data:
            [
                {
                    'date': '2024-01-15',
                    'type': 'BUY',
                    'ticker': 'AAPL',
                    'company_name': 'Apple Inc.',
                    'sector': 'Technology',
                    'quantity': 10,
                    'price': 150.25,
                    'fees': 5.00,
                    'currency': 'USD',
                    'notes': 'Imported via...'
                },
                ...
            ]
        """
        # Build query
        query = Transaction.query.filter_by(user_id=self.user_id)

        # Apply date filters
        if start_date:
            query = query.filter(Transaction.date >= start_date)
        if end_date:
            query = query.filter(Transaction.date <= end_date)

        # Order by date ascending (chronological for LLM to analyze patterns)
        query = query.join(Company).order_by(Transaction.date.asc())

        transactions = query.all()

        # If excluding positions opened before start_date
        if exclude_positions_opened_before and start_date:
            transactions = self._filter_exclude_old_positions(transactions, start_date)

        # Convert to raw dict format
        raw_data = []
        for txn in transactions:
            # Get sector name (handle Sector object or string)
            sector_name = 'Unknown'
            if txn.company and txn.company.sector:
                sector_name = txn.company.sector.name if hasattr(txn.company.sector, 'name') else str(txn.company.sector)

            raw_data.append({
                'date': txn.date.isoformat(),
                'type': txn.type,
                'ticker': txn.company.ticker_symbol if txn.company else 'Unknown',
                'company_name': txn.company.name if txn.company else 'Unknown',
                'sector': sector_name,
                'quantity': int(txn.quantity) if txn.quantity else 0,
                'price': float(txn.price_per_share) if txn.price_per_share else 0.0,
                'fees': float(txn.fees) if txn.fees else 0.0,
                'currency': txn.currency or (txn.company.reporting_currency if txn.company else None) or 'USD',
                'notes': txn.notes or ''
            })

        return raw_data

    def _filter_exclude_old_positions(
        self,
        transactions: List[Transaction],
        start_date: date
    ) -> List[Transaction]:
        """
        Filter out transactions for positions opened before start_date.

        Motivation: When analyzing trading skills in 2024, exclude positions
        opened in 2023 (even if sold in 2024) to focus on decisions made
        within the timeframe.

        Args:
            transactions: All transactions in date range
            start_date: Cutoff date

        Returns:
            Filtered transaction list
        """
        # Find first BUY date for each company
        company_first_buy = {}

        # Need to check ALL transactions, not just filtered ones
        all_txns = Transaction.query.filter_by(
            user_id=self.user_id
        ).order_by(Transaction.date.asc()).all()

        for txn in all_txns:
            if txn.type == 'BUY' and txn.company_id not in company_first_buy:
                company_first_buy[txn.company_id] = txn.date

        # Filter: keep only transactions for positions opened >= start_date
        filtered = [
            txn for txn in transactions
            if txn.company_id in company_first_buy
            and company_first_buy[txn.company_id] >= start_date
        ]

        logger.info(
            f"Filtered {len(transactions)} → {len(filtered)} transactions "
            f"(excluded positions opened before {start_date})"
        )

        return filtered

    # ================================================================
    # STRUCTURED METRICS EXTRACTION (Pre-calculated)
    # ================================================================

    def extract_all(self) -> Dict[str, Any]:
        """
        Extract complete portfolio data with pre-calculated metrics.

        Returns:
            Dict with:
            - portfolio_summary: High-level metrics
            - positions: Active position details
            - closed_positions: Realized trade outcomes
            - trading_patterns: Behavioral patterns
            - sector_breakdown: Allocation by sector
            - recent_activity: Last 90 days
            - metadata: Timestamps and counts
        """
        # Load data once
        positions = self._load_positions()
        transactions = self._load_transactions()

        return {
            'portfolio_summary': self.extract_portfolio_summary(positions, transactions),
            'positions': self.extract_active_positions(positions),
            'closed_positions': self.extract_closed_positions(positions),
            'trading_patterns': self.extract_trading_patterns(transactions),
            'sector_breakdown': self.extract_sector_breakdown(positions),
            'recent_activity': self.extract_recent_activity(transactions, days=90),
            'metadata': {
                'total_transactions': len(transactions),
                'extraction_date': now_utc().isoformat(),
                'user_id': self.user_id,
                'has_data': len(transactions) > 0
            }
        }

    def extract_portfolio_summary(
        self,
        positions: List[PortfolioPosition],
        transactions: List[Transaction]
    ) -> Dict[str, Any]:
        """
        Calculate high-level portfolio metrics.

        Returns:
            Dict with win rate, total invested, realized gains/losses, CAGR
        """
        active_positions = [p for p in positions if p.is_active]
        closed_positions = [p for p in positions if not p.is_active]

        # Total invested in active positions
        total_invested = sum(
            float(p.total_cost) if p.total_cost else 0
            for p in active_positions
        )

        # Realized gains from closed positions
        total_realized_gl = sum(
            float(p.realized_gain_loss) if p.realized_gain_loss else 0
            for p in closed_positions
        )

        # Win/loss counts
        wins = len([p for p in closed_positions if p.realized_gain_loss and p.realized_gain_loss > 0])
        losses = len([p for p in closed_positions if p.realized_gain_loss and p.realized_gain_loss <= 0])
        total_closed = wins + losses

        # Calculate CAGR
        cagr = self._calculate_portfolio_cagr(positions, transactions)

        return {
            'total_positions': len(active_positions),
            'closed_positions': len(closed_positions),
            'total_invested': round(total_invested, 2),
            'total_realized_gain_loss': round(total_realized_gl, 2),
            'win_rate': round(wins / total_closed * 100, 1) if total_closed > 0 else 0.0,
            'wins': wins,
            'losses': losses,
            'total_transactions': len(transactions),
            'cagr': cagr
        }

    def extract_active_positions(self, positions: List[PortfolioPosition]) -> List[Dict[str, Any]]:
        """
        Extract details of active positions.

        Returns:
            List of dicts with ticker, sector, cost, hold time
        """
        active = [p for p in positions if p.is_active and p.company]

        summaries = []
        for position in active:
            # Calculate hold time
            hold_days = 0
            if position.first_purchase_date:
                hold_days = (date.today() - position.first_purchase_date).days

            # Get sector name (handle Sector object or string)
            sector_name = 'Unknown'
            if position.company.sector:
                sector_name = position.company.sector.name if hasattr(position.company.sector, 'name') else str(position.company.sector)

            summaries.append({
                'ticker': position.company.ticker_symbol,
                'company_name': position.company.name,
                'sector': sector_name,
                'shares': int(position.total_shares) if position.total_shares else 0,
                'avg_cost': float(position.average_cost_basis) if position.average_cost_basis else 0,
                'total_invested': float(position.total_cost) if position.total_cost else 0,
                'hold_days': hold_days,
                'purchase_date': position.first_purchase_date.isoformat() if position.first_purchase_date else None
            })

        # Sort by total invested descending
        summaries.sort(key=lambda x: x['total_invested'], reverse=True)

        return summaries

    def extract_closed_positions(self, positions: List[PortfolioPosition]) -> List[Dict[str, Any]]:
        """
        Extract details of closed positions (realized trades).

        Returns:
            List of dicts with realized gain/loss, return %, hold time
        """
        closed = [p for p in positions if not p.is_active and p.company and p.realized_gain_loss]

        summaries = []
        for position in closed:
            # Calculate hold time
            hold_days = 0
            if position.first_purchase_date and position.last_transaction_date:
                hold_days = (position.last_transaction_date - position.first_purchase_date).days

            # Calculate return percentage
            return_pct = 0
            if position.total_cost and position.total_cost > 0:
                return_pct = round(
                    float(position.realized_gain_loss) / float(position.total_cost) * 100,
                    1
                )

            # Get sector name (handle Sector object or string)
            sector_name = 'Unknown'
            if position.company.sector:
                sector_name = position.company.sector.name if hasattr(position.company.sector, 'name') else str(position.company.sector)

            summaries.append({
                'ticker': position.company.ticker_symbol,
                'company_name': position.company.name,
                'sector': sector_name,
                'realized_gain_loss': float(position.realized_gain_loss),
                'return_pct': return_pct,
                'hold_days': hold_days,
                'was_winner': position.realized_gain_loss > 0
            })

        # Sort by realized gain/loss descending
        summaries.sort(key=lambda x: x['realized_gain_loss'], reverse=True)

        return summaries

    def extract_trading_patterns(self, transactions: List[Transaction]) -> Dict[str, Any]:
        """
        Extract behavioral patterns from transaction history.

        Returns:
            Dict with averages, frequencies, most-traded companies, winners vs losers
        """
        if not transactions:
            return {
                'total_buys': 0,
                'total_sells': 0,
                'avg_hold_time_days': 0,
                'avg_hold_days': 0,
                'transactions_per_month': 0,
                'most_traded_companies': [],
                'avg_winner_return': 0,
                'avg_winner_hold_days': 0,
                'avg_loser_return': 0,
                'avg_loser_hold_days': 0
            }

        buys = [t for t in transactions if t.type == 'BUY']
        sells = [t for t in transactions if t.type == 'SELL']

        # Calculate average hold time
        hold_times = self._calculate_hold_times(transactions)
        avg_hold_days = round(sum(hold_times) / len(hold_times)) if hold_times else 0

        # Transaction frequency
        date_range = (transactions[0].date - transactions[-1].date).days
        txns_per_month = len(transactions) / (date_range / 30) if date_range > 0 else 0

        # Most traded companies
        most_traded = self._get_most_traded_companies(transactions, limit=5)

        # Winners vs losers comparison
        positions = self._load_positions()
        winners_vs_losers = self._calculate_winners_vs_losers(positions, transactions)

        return {
            'total_buys': len(buys),
            'total_sells': len(sells),
            'avg_hold_time_days': avg_hold_days,  # Legacy key
            'avg_hold_days': avg_hold_days,       # New consistent key
            'transactions_per_month': round(txns_per_month, 1),
            'most_traded_companies': most_traded,
            # Winners vs Losers metrics
            'avg_winner_return': round(winners_vs_losers['avg_winner_return'], 1),
            'avg_winner_hold_days': round(winners_vs_losers['avg_winner_hold_days']),
            'avg_loser_return': round(winners_vs_losers['avg_loser_return'], 1),
            'avg_loser_hold_days': round(winners_vs_losers['avg_loser_hold_days'])
        }

    def extract_sector_breakdown(self, positions: List[PortfolioPosition]) -> List[Dict[str, Any]]:
        """
        Calculate portfolio allocation by sector.

        Returns:
            List of sector breakdowns with {sector, total_cost, position_count, percentage}
        """
        sector_allocation = {}
        total_invested = 0

        for position in positions:
            if position.is_active and position.company and position.total_cost:
                # Get sector name (handle Sector object or string)
                sector_name = 'Unknown'
                if position.company.sector:
                    sector_name = position.company.sector.name if hasattr(position.company.sector, 'name') else str(position.company.sector)

                cost = float(position.total_cost)

                if sector_name not in sector_allocation:
                    sector_allocation[sector_name] = {
                        'sector': sector_name,
                        'total_cost': 0,
                        'position_count': 0
                    }

                sector_allocation[sector_name]['total_cost'] += cost
                sector_allocation[sector_name]['position_count'] += 1
                total_invested += cost

        # Calculate percentages and convert to list
        sector_list = []
        for sector_name, data in sector_allocation.items():
            data['percentage'] = round(
                data['total_cost'] / total_invested * 100, 1
            ) if total_invested > 0 else 0
            data['total_cost'] = round(data['total_cost'], 2)
            sector_list.append(data)

        # Sort by total_cost descending
        sector_list.sort(key=lambda x: x['total_cost'], reverse=True)

        return sector_list

    def extract_recent_activity(
        self,
        transactions: List[Transaction],
        days: int = 90
    ) -> List[Dict[str, Any]]:
        """
        Extract recent transaction activity.

        Args:
            transactions: All transactions
            days: Number of days to look back

        Returns:
            List of recent transactions (up to 20)
        """
        cutoff_date = date.today() - timedelta(days=days)
        recent = [t for t in transactions if t.date >= cutoff_date]

        activity = []
        for txn in recent[:20]:  # Limit to 20 most recent
            activity.append({
                'date': txn.date.isoformat(),
                'type': txn.type,
                'ticker': txn.company.ticker_symbol if txn.company else 'Unknown',
                'company': txn.company.name if txn.company else 'Unknown',
                'quantity': int(txn.quantity) if txn.quantity else 0,
                'price': float(txn.price_per_share) if txn.price_per_share else 0
            })

        return activity

    def calculate_performance_chart_data(
        self,
        transactions: List[Transaction],
        time_periods: int = 12
    ) -> Dict[str, Any]:
        """
        Calculate portfolio value and cost over time for chart visualization.

        Uses HISTORICAL prices for each time period (not current prices).
        This ensures accurate performance tracking.

        Args:
            transactions: All transactions
            time_periods: Number of time periods to calculate (default 12 months)

        Returns:
            Dict with labels, current_values, and total_costs arrays
        """
        from collections import defaultdict
        from calendar import monthrange
        from app.utils.financial_utils import get_historical_prices_multi
        import logging

        logger = logging.getLogger(__name__)

        today = date.today()

        # Generate month labels and end dates
        labels = []
        period_ends = []

        for i in range(time_periods - 1, -1, -1):
            # Calculate month by going back i months from today
            year = today.year
            month = today.month - i

            # Handle year wraparound
            while month <= 0:
                month += 12
                year -= 1

            # Get last day of the month
            last_day = monthrange(year, month)[1]
            period_end = date(year, month, last_day)

            # Don't go beyond today
            if period_end > today:
                period_end = today

            labels.append(date(year, month, 1).strftime('%b'))
            period_ends.append(period_end)

        # Collect all unique tickers from transactions
        unique_tickers = set()
        for txn in transactions:
            if txn.company and txn.company.ticker_symbol:
                unique_tickers.add(txn.company.ticker_symbol)

        # Get CURRENT prices for all positions (for today's value)
        positions = self._load_positions()
        current_prices = {}
        for pos in positions:
            if pos.company and pos.company.ticker_symbol:
                ticker = pos.company.ticker_symbol
                # Use current_price from position (already cached)
                if pos.current_price:
                    current_prices[ticker] = float(pos.current_price)

        logger.info(f"Loaded {len(current_prices)} current prices for today's portfolio value")

        # Fetch HISTORICAL prices for all tickers at all period ends
        # This uses cached provider - first run fetches, subsequent runs are instant
        logger.info(f"Fetching historical prices for {len(unique_tickers)} tickers across {len(period_ends)} periods")
        historical_prices = get_historical_prices_multi(
            tickers=list(unique_tickers),
            price_dates=period_ends
        )

        # Log summary of historical prices fetched
        total_historical_prices = sum(len(prices) for prices in historical_prices.values())
        logger.info(f"Historical prices fetched: {total_historical_prices} price points across {len(historical_prices)} tickers")

        # Diagnose tickers with no data
        tickers_with_no_data = [ticker for ticker in unique_tickers if not historical_prices.get(ticker)]
        tickers_with_sparse_data = [(ticker, len(prices)) for ticker, prices in historical_prices.items() if len(prices) < len(period_ends) // 2]
        if tickers_with_no_data:
            logger.warning(f"{len(tickers_with_no_data)} tickers have NO historical data from Yahoo Finance: {tickers_with_no_data[:5]}")
        if tickers_with_sparse_data:
            logger.warning(f"{len(tickers_with_sparse_data)} tickers have sparse data: {tickers_with_sparse_data[:5]}")

        # Sort transactions by date
        sorted_txns = sorted(transactions, key=lambda t: t.date)

        # Calculate cumulative values for each period
        current_values = []
        total_costs = []

        # Track positions over time (ticker -> {quantity, cost_basis})
        cumulative_positions = defaultdict(lambda: {'quantity': 0, 'cost_basis': 0})
        txn_idx = 0

        for period_end in period_ends:
            # Process all transactions up to this period end
            while txn_idx < len(sorted_txns) and sorted_txns[txn_idx].date <= period_end:
                txn = sorted_txns[txn_idx]
                ticker = txn.company.ticker_symbol if txn.company else 'Unknown'
                txn_type = txn.type.lower() if txn.type else ''

                if txn_type == 'buy':
                    qty = float(txn.quantity) if txn.quantity else 0
                    price = float(txn.price_per_share) if txn.price_per_share else 0
                    fee = float(txn.fees) if txn.fees else 0

                    cumulative_positions[ticker]['quantity'] += qty
                    cumulative_positions[ticker]['cost_basis'] += (qty * price + fee)

                elif txn_type == 'sell':
                    qty = float(txn.quantity) if txn.quantity else 0

                    if cumulative_positions[ticker]['quantity'] > 0:
                        # Calculate cost basis per share
                        cost_per_share = cumulative_positions[ticker]['cost_basis'] / cumulative_positions[ticker]['quantity']
                        # Reduce cost basis proportionally
                        cumulative_positions[ticker]['cost_basis'] -= (qty * cost_per_share)
                        cumulative_positions[ticker]['quantity'] -= qty

                        # Clean up if quantity is zero
                        if cumulative_positions[ticker]['quantity'] <= 0:
                            cumulative_positions[ticker]['cost_basis'] = 0
                            cumulative_positions[ticker]['quantity'] = 0

                # Note: DIVIDEND transactions don't affect quantity or cost basis

                txn_idx += 1

            # Calculate total cost (sum of all cost bases)
            period_total_cost = sum(pos['cost_basis'] for pos in cumulative_positions.values())
            total_costs.append(round(period_total_cost, 2))

            # Calculate portfolio value
            # For TODAY: use current prices (real-time)
            # For HISTORY: use historical prices (accurate past performance)
            is_current_period = (period_end == today)

            period_current_value = 0
            price_sources = {'current': 0, 'historical_exact': 0, 'historical_nearest': 0, 'cost_basis': 0}

            for ticker, pos_data in cumulative_positions.items():
                if pos_data['quantity'] > 0:
                    price_to_use = None
                    price_source = None

                    if is_current_period:
                        # Use current/real-time price for today
                        price_to_use = current_prices.get(ticker)
                        if price_to_use:
                            price_source = 'current'
                            logger.debug(f"[{period_end}] {ticker}: Using CURRENT price ${price_to_use:.2f}")

                    if price_to_use is None:
                        # Use historical price for past periods (or fallback for current if no current price)
                        ticker_prices = historical_prices.get(ticker, {})

                        # Try to get exact date first
                        price_to_use = ticker_prices.get(period_end)
                        if price_to_use:
                            price_source = 'historical_exact'

                        # If exact date not available (weekend/holiday), find nearest
                        if price_to_use is None and ticker_prices:
                            # Find closest available date within 7 days
                            closest_date = None
                            min_days_diff = float('inf')

                            for available_date in ticker_prices.keys():
                                days_diff = abs((available_date - period_end).days)
                                if days_diff <= 7 and days_diff < min_days_diff:
                                    min_days_diff = days_diff
                                    closest_date = available_date

                            if closest_date:
                                price_to_use = ticker_prices[closest_date]
                                price_source = 'historical_nearest'
                                logger.debug(f"[{period_end}] {ticker}: Using nearest price from {closest_date}")

                    if price_to_use is not None:
                        # Use the price we found
                        value_contribution = pos_data['quantity'] * price_to_use
                        period_current_value += value_contribution
                        price_sources[price_source] += 1
                        logger.debug(f"[{period_end}] {ticker}: {pos_data['quantity']} shares × ${price_to_use:.2f} = ${value_contribution:.2f} ({price_source})")
                    else:
                        # Last resort: use cost basis if no price available at all
                        price_source = 'cost_basis'
                        price_sources[price_source] += 1
                        period_current_value += pos_data['cost_basis']
                        logger.warning(f"[{period_end}] {ticker}: No price available, using cost basis ${pos_data['cost_basis']:.2f}")

            # Log summary for this period
            logger.info(f"[{period_end}] Portfolio value: ${period_current_value:,.2f} | Cost: ${period_total_cost:,.2f} | Sources: {dict(price_sources)}")

            current_values.append(round(period_current_value, 2))

        return {
            'labels': labels,
            'current_values': current_values,
            'total_costs': total_costs
        }

    # ================================================================
    # Helper Methods
    # ================================================================

    def _load_positions(self) -> List[PortfolioPosition]:
        """Load all portfolio positions"""
        return PortfolioPosition.query.filter_by(
            user_id=self.user_id
        ).join(Company).all()

    def _load_transactions(self) -> List[Transaction]:
        """Load all transactions ordered by date descending"""
        return Transaction.query.filter_by(
            user_id=self.user_id
        ).join(Company).order_by(Transaction.date.desc()).all()

    def _calculate_hold_times(self, transactions: List[Transaction]) -> List[int]:
        """Calculate hold times by matching buys and sells"""
        hold_times = []
        company_first_buy = {}

        for txn in sorted(transactions, key=lambda t: t.date):
            if txn.type == 'BUY' and txn.company_id not in company_first_buy:
                company_first_buy[txn.company_id] = txn.date
            elif txn.type == 'SELL' and txn.company_id in company_first_buy:
                first_buy = company_first_buy[txn.company_id]
                hold_days = (txn.date - first_buy).days
                hold_times.append(hold_days)

        return hold_times

    def _get_most_traded_companies(
        self,
        transactions: List[Transaction],
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get companies with most transaction activity"""
        company_txn_count = {}

        for txn in transactions:
            if txn.company:
                ticker = txn.company.ticker_symbol
                if ticker not in company_txn_count:
                    company_txn_count[ticker] = {
                        'ticker': ticker,
                        'name': txn.company.name,
                        'transaction_count': 0
                    }
                company_txn_count[ticker]['transaction_count'] += 1

        # Sort by transaction count
        sorted_companies = sorted(
            company_txn_count.values(),
            key=lambda x: x['transaction_count'],
            reverse=True
        )

        return sorted_companies[:limit]

    def _calculate_winners_vs_losers(self, positions: List[PortfolioPosition], transactions: List[Transaction]) -> Dict[str, Any]:
        """
        Calculate comparison metrics for winning vs losing positions.

        Args:
            positions: List of portfolio positions
            transactions: List of all transactions (needed to calculate original cost basis)

        Returns:
            Dict with avg returns, hold times for winners and losers
        """
        closed_positions = [p for p in positions if not p.is_active]

        winners = []
        losers = []

        for position in closed_positions:
            if not position.realized_gain_loss:
                continue

            gl = float(position.realized_gain_loss)

            # Calculate hold time
            hold_days = 0
            if position.first_purchase_date and position.last_transaction_date:
                hold_days = (position.last_transaction_date - position.first_purchase_date).days

            # Calculate return percentage for closed positions
            # For closed positions, total_cost is 0 (FIFO reduces it as shares are sold)
            # We need to get all transactions to calculate original cost basis
            return_pct = 0

            # Get all transactions for this position
            company_transactions = [t for t in transactions if t.company_id == position.company_id]

            if company_transactions:
                # Calculate total buy cost (original investment)
                total_buy_cost = sum(
                    float(t.quantity) * float(t.price_per_share) + float(t.fees)
                    for t in company_transactions
                    if t.type == 'BUY'
                )

                if total_buy_cost > 0:
                    return_pct = (gl / total_buy_cost) * 100

            position_data = {
                'hold_days': hold_days,
                'return_pct': return_pct,
                'gain_loss': gl
            }

            if gl > 0:
                winners.append(position_data)
            else:
                losers.append(position_data)

        # Calculate averages for winners
        avg_winner_return = 0
        avg_winner_hold_days = 0
        if winners:
            avg_winner_return = sum(p['return_pct'] for p in winners) / len(winners)
            avg_winner_hold_days = sum(p['hold_days'] for p in winners) / len(winners)

        # Calculate averages for losers
        avg_loser_return = 0
        avg_loser_hold_days = 0
        if losers:
            avg_loser_return = sum(p['return_pct'] for p in losers) / len(losers)
            avg_loser_hold_days = sum(p['hold_days'] for p in losers) / len(losers)

        return {
            'win_count': len(winners),
            'loss_count': len(losers),
            'avg_winner_return': avg_winner_return,
            'avg_winner_hold_days': avg_winner_hold_days,
            'avg_loser_return': avg_loser_return,
            'avg_loser_hold_days': avg_loser_hold_days
        }

    def _calculate_portfolio_cagr(self, positions: List[PortfolioPosition], transactions: List[Transaction]) -> float:
        """
        Calculate portfolio-level CAGR using the existing financial utilities.

        Returns:
            CAGR as a percentage (e.g., 15.5 for 15.5%)
        """
        if not transactions:
            return 0.0

        # Get first and last transaction dates
        sorted_transactions = sorted(transactions, key=lambda t: t.date)
        first_date = sorted_transactions[0].date
        last_date = sorted_transactions[-1].date
        days_held = (last_date - first_date).days

        # Calculate NET cash invested (money in - money out)
        # This accounts for proceeds from sells being reinvested or withdrawn
        total_buys = sum(
            t.total_value
            for t in transactions
            if t.type == 'BUY'
        )

        total_sells = sum(
            (float(t.quantity) * float(t.price_per_share))
            for t in transactions
            if t.type == 'SELL'
        )

        net_invested = total_buys - total_sells

        # If net is negative or zero, user withdrew more than invested
        if net_invested <= 0:
            # Use total buys as baseline if user withdrew profits
            net_invested = total_buys if total_buys > 0 else 1

        # Calculate current portfolio value
        # = market value of active positions + realized gains still in portfolio
        active_value = sum(
            float(p.current_value) if p.current_value else float(p.total_cost) if p.total_cost else 0
            for p in positions if p.is_active
        )

        # Add back realized gains from closed positions (assuming not withdrawn)
        # This represents profit that's either reinvested or held as cash
        realized_gains = sum(
            float(p.realized_gain_loss) if p.realized_gain_loss else 0
            for p in positions if not p.is_active
        )

        ending_value = active_value + realized_gains

        # Calculate total return percentage
        total_return_pct = calculate_total_return(net_invested, ending_value)

        # Calculate CAGR using the utility
        cagr = calculate_cagr(total_return_pct, days_held)

        return round(cagr, 1)
