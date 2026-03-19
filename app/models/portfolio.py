# app/models/portfolio.py

from datetime import datetime
from decimal import Decimal
from app import db
from app.utils.time_utils import now_utc
from app.models.company import Company


class ExchangeRate(db.Model):
    """
    Cache for exchange rates to minimize API calls and provide historical rates.
    Stores daily exchange rates for currency conversions.
    """
    __tablename__ = 'exchange_rate'

    id = db.Column(db.Integer, primary_key=True)
    from_currency = db.Column(db.String(3), nullable=False, index=True)  # EUR, GBP, JPY
    to_currency = db.Column(db.String(3), nullable=False, index=True)    # Usually user's base currency
    rate = db.Column(db.Numeric(10, 6), nullable=False)  # Conversion rate (6 decimals for JPY, etc.)
    date = db.Column(db.Date, nullable=False, index=True)  # Rate for this date
    source = db.Column(db.String(50), nullable=True)  # API source (e.g., 'yahoo', 'exchangerate-api')
    fetched_at = db.Column(db.DateTime, default=now_utc, nullable=False)

    # Ensure one rate per currency pair per date
    __table_args__ = (
        db.UniqueConstraint('from_currency', 'to_currency', 'date', name='uq_currency_pair_date'),
        db.Index('idx_exchange_rate_lookup', 'from_currency', 'to_currency', 'date'),
    )

    def __repr__(self):
        return f'<ExchangeRate {self.from_currency}/{self.to_currency} @ {self.rate} on {self.date}>'


class Transaction(db.Model):
    """
    Records all portfolio transactions: buys, sells, dividends, splits, spinoffs.
    This is the source of truth for portfolio position calculations using FIFO method.
    """
    __tablename__ = 'transaction'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=True, index=True)  # Nullable for DEPOSIT/WITHDRAWAL
    decision_journal_id = db.Column(db.Integer, db.ForeignKey('decision_journal.id'), nullable=True)

    # Transaction details
    type = db.Column(db.String(20), nullable=False, index=True)
    # Valid types: 'BUY', 'SELL', 'DIVIDEND', 'SPLIT', 'SPINOFF', 'DEPOSIT', 'WITHDRAWAL'

    date = db.Column(db.Date, nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=True)  # Whole shares only; NULL for DEPOSIT/WITHDRAWAL

    # MULTI-CURRENCY SUPPORT
    # Primary currency (detected from ticker or user-specified)
    currency = db.Column(db.String(3), nullable=False, default='USD', index=True)  # ISO 4217: USD, EUR, GBP, JPY

    # Legacy fields (kept for backward compatibility, will be same as currency fields for old data)
    price_per_share = db.Column(db.Numeric(10, 2), nullable=True)  # NULL for DEPOSIT/WITHDRAWAL
    fees = db.Column(db.Numeric(10, 2), default=0.00)

    # Cash transaction amount (for DEPOSIT/WITHDRAWAL only)
    cash_amount = db.Column(db.Numeric(12, 2), nullable=True)
    cash_amount_base = db.Column(db.Numeric(12, 2), nullable=True)  # In user's base currency

    # Base currency values (converted for portfolio calculations)
    price_per_share_base = db.Column(db.Numeric(10, 2), nullable=True)
    fees_base = db.Column(db.Numeric(10, 2), nullable=True)
    exchange_rate = db.Column(db.Numeric(10, 6), nullable=True)  # Rate used for conversion
    exchange_rate_date = db.Column(db.Date, nullable=True)  # Date of exchange rate used

    # Additional context
    notes = db.Column(db.Text, nullable=True)

    # Pattern tracking: Buying without research
    bought_without_research = db.Column(db.Boolean, default=False, index=True)
    reason_without_research = db.Column(db.Text, nullable=True)

    # Adding to existing position tracking
    is_add_to_position = db.Column(db.Boolean, default=False, index=True)
    add_position_reason = db.Column(db.String(50), nullable=True)
    # Valid reasons: 'price_drop', 'extra_cash', 'increased_confidence', 'averaging_down', 'other'
    add_position_notes = db.Column(db.Text, nullable=True)
    thesis_updated = db.Column(db.Boolean, default=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=now_utc, nullable=False)
    updated_at = db.Column(db.DateTime, default=now_utc, onupdate=now_utc, nullable=False)

    # Relationships
    user = db.relationship('User', backref=db.backref('transactions', lazy='dynamic', cascade='all, delete-orphan'))
    company = db.relationship('Company', backref=db.backref('transactions', lazy='dynamic'))
    decision_journal = db.relationship('DecisionJournal', backref=db.backref('transactions', lazy='dynamic'))

    def __repr__(self):
        if self.type in ('DEPOSIT', 'WITHDRAWAL'):
            return f'<Transaction {self.type} {self.cash_amount} on {self.date}>'
        return f'<Transaction {self.type} {self.quantity} shares of {self.company_id} on {self.date}>'

    @property
    def total_value(self):
        """Calculate total transaction value including fees"""
        if self.type in ('DEPOSIT', 'WITHDRAWAL'):
            return float(self.cash_amount or 0)
        return float(self.quantity * self.price_per_share) + float(self.fees)

    def to_dict(self):
        """Convert transaction to dictionary for API responses"""
        result = {
            'id': self.id,
            'type': self.type,
            'date': self.date.isoformat() if self.date else None,
            'quantity': self.quantity,
            'price_per_share': float(self.price_per_share) if self.price_per_share else None,
            'fees': float(self.fees) if self.fees else 0,
            'total_value': self.total_value,
            'notes': self.notes,
            'bought_without_research': self.bought_without_research,
            'company': {
                'id': self.company.id,
                'name': self.company.name,
                'ticker': self.company.ticker_symbol
            } if self.company else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        if self.type in ('DEPOSIT', 'WITHDRAWAL'):
            result['cash_amount'] = float(self.cash_amount) if self.cash_amount else 0
        return result


class PortfolioPosition(db.Model):
    """
    Aggregated view of current portfolio positions.
    This is a calculated/cached table updated whenever transactions occur.
    Uses FIFO method for cost basis calculation.
    """
    __tablename__ = 'portfolio_position'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False, index=True)

    # Position data (calculated from transactions using FIFO)
    total_shares = db.Column(db.Integer, default=0, nullable=False)

    # MULTI-CURRENCY SUPPORT
    currency = db.Column(db.String(3), nullable=False, default='USD', index=True)  # Position's native currency

    # Legacy fields (in original currency for backward compatibility)
    average_cost_basis = db.Column(db.Numeric(10, 2), nullable=True)  # Per share in original currency
    total_cost = db.Column(db.Numeric(12, 2), default=0.00, nullable=False)  # Total invested in original currency
    current_price = db.Column(db.Numeric(10, 2), nullable=True)  # Current price in original currency
    current_value = db.Column(db.Numeric(12, 2), nullable=True)  # Current value in original currency

    # Base currency values (converted to user's base currency)
    average_cost_basis_base = db.Column(db.Numeric(10, 2), nullable=True)
    total_cost_base = db.Column(db.Numeric(12, 2), nullable=True)
    current_price_base = db.Column(db.Numeric(10, 2), nullable=True)
    current_value_base = db.Column(db.Numeric(12, 2), nullable=True)

    # Exchange rate info
    current_exchange_rate = db.Column(db.Numeric(10, 6), nullable=True)
    last_exchange_rate_update = db.Column(db.DateTime, nullable=True)

    # Unrealized gains/losses (in base currency)
    unrealized_gain_loss = db.Column(db.Numeric(12, 2), nullable=True)
    unrealized_gain_loss_pct = db.Column(db.Numeric(6, 2), nullable=True)

    # Currency-specific gains/losses (separate from stock performance)
    currency_gain_loss = db.Column(db.Numeric(12, 2), default=0.00, nullable=False)
    currency_gain_loss_pct = db.Column(db.Numeric(6, 2), default=0.00, nullable=False)

    # Realized gains/losses (from sells - cumulative, in base currency)
    realized_gain_loss = db.Column(db.Numeric(12, 2), default=0.00, nullable=False)
    realized_gain_loss_pct = db.Column(db.Numeric(6, 2), nullable=True)

    # Metadata
    first_purchase_date = db.Column(db.Date, nullable=True, index=True)
    last_transaction_date = db.Column(db.Date, nullable=True)
    last_price_update = db.Column(db.DateTime, nullable=True)

    # Position status
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    # False when total_shares = 0 (fully exited)

    # Timestamps
    created_at = db.Column(db.DateTime, default=now_utc, nullable=False)
    updated_at = db.Column(db.DateTime, default=now_utc, onupdate=now_utc, nullable=False)

    # Ensure one position per user per company
    __table_args__ = (
        db.UniqueConstraint('user_id', 'company_id', name='uq_user_company_position'),
    )

    # Relationships
    user = db.relationship('User', backref=db.backref('portfolio_positions', lazy='dynamic', cascade='all, delete-orphan'))
    company = db.relationship('Company', backref=db.backref('portfolio_positions', lazy='dynamic'))

    def __repr__(self):
        return f'<PortfolioPosition {self.company_id}: {self.total_shares} shares @ ${self.average_cost_basis}>'

    @property
    def days_held(self):
        """Calculate number of days position has been held"""
        if not self.first_purchase_date:
            return 0
        return (datetime.now().date() - self.first_purchase_date).days

    @property
    def allocation_percentage(self):
        """Calculate position allocation % (requires total portfolio value from user)"""
        # This will be calculated at the view/controller level
        return None

    def update_market_data(self, current_price):
        """
        Update current market price and recalculate values.
        Called by PriceService when fetching from Yahoo Finance.
        """
        self.current_price = Decimal(str(current_price))
        self.current_value = self.total_shares * self.current_price

        if self.total_cost > 0:
            self.unrealized_gain_loss = self.current_value - self.total_cost
            self.unrealized_gain_loss_pct = (self.unrealized_gain_loss / self.total_cost) * 100
        else:
            self.unrealized_gain_loss = Decimal('0.00')
            self.unrealized_gain_loss_pct = Decimal('0.00')

        self.last_price_update = now_utc()

    def to_dict(self):
        """Convert position to dictionary for API responses"""
        return {
            'id': self.id,
            'total_shares': self.total_shares,
            'average_cost_basis': float(self.average_cost_basis) if self.average_cost_basis else None,
            'total_cost': float(self.total_cost),
            'current_price': float(self.current_price) if self.current_price else None,
            'current_value': float(self.current_value) if self.current_value else None,
            'unrealized_gain_loss': float(self.unrealized_gain_loss) if self.unrealized_gain_loss else None,
            'unrealized_gain_loss_pct': float(self.unrealized_gain_loss_pct) if self.unrealized_gain_loss_pct else None,
            'realized_gain_loss': float(self.realized_gain_loss),
            'realized_gain_loss_pct': float(self.realized_gain_loss_pct) if self.realized_gain_loss_pct else None,
            'days_held': self.days_held,
            'first_purchase_date': self.first_purchase_date.isoformat() if self.first_purchase_date else None,
            'last_price_update': self.last_price_update.isoformat() if self.last_price_update else None,
            'is_active': self.is_active,
            'company': {
                'id': self.company.id,
                'name': self.company.name,
                'ticker': self.company.ticker_symbol,
                'sector': self.company.sector.name if self.company.sector else None,
                'industry': self.company.industry
            } if self.company else None
        }


# Helper functions for FIFO cost basis calculation

def _get_base_price(txn):
    """Get price in base currency, falling back to original if _base not set."""
    if txn.price_per_share_base is not None:
        return Decimal(str(txn.price_per_share_base))
    return Decimal(str(txn.price_per_share))


def _get_base_fees(txn):
    """Get fees in base currency, falling back to original if _base not set."""
    if txn.fees_base is not None:
        return Decimal(str(txn.fees_base))
    return Decimal(str(txn.fees))


def calculate_fifo_cost_basis(company_id, user_id):
    """
    Calculate cost basis using FIFO (First In, First Out) method.

    Uses base currency values (_base fields) when available, falling back
    to original currency values for backward compatibility. This ensures
    all calculations are in the user's base currency.

    Returns:
        tuple: (total_shares, avg_cost_basis, total_cost, realized_gain_loss, first_purchase_date)
    """
    transactions = Transaction.query.filter_by(
        company_id=company_id,
        user_id=user_id
    ).order_by(Transaction.date.asc(), Transaction.id.asc()).all()

    # FIFO queue: [(date, quantity, price_per_share), ...]
    shares_queue = []
    total_shares = 0
    total_cost = Decimal('0.00')
    realized_gain_loss = Decimal('0.00')
    first_purchase_date = None

    for txn in transactions:
        price = _get_base_price(txn)
        fees = _get_base_fees(txn)

        if txn.type == 'BUY':
            # Add to queue
            shares_queue.append({
                'date': txn.date,
                'quantity': txn.quantity,
                'price_per_share': price,
                'fees': fees
            })

            total_shares += txn.quantity
            total_cost += (Decimal(str(txn.quantity)) * price) + fees

            # Track first purchase
            if first_purchase_date is None:
                first_purchase_date = txn.date

        elif txn.type == 'SELL':
            shares_to_sell = txn.quantity
            sell_proceeds = (Decimal(str(txn.quantity)) * price) - fees
            sell_cost_basis = Decimal('0.00')

            # Remove shares from front of queue (FIFO)
            while shares_to_sell > 0 and shares_queue:
                batch = shares_queue[0]
                batch_qty = batch['quantity']
                batch_price = batch['price_per_share']
                batch_fees_per_share = batch['fees'] / batch['quantity'] if batch['quantity'] > 0 else Decimal('0.00')

                if batch_qty <= shares_to_sell:
                    # Sell entire batch
                    shares_queue.pop(0)
                    shares_to_sell -= batch_qty
                    total_shares -= batch_qty

                    batch_cost = (batch_qty * batch_price) + batch['fees']
                    total_cost -= batch_cost
                    sell_cost_basis += batch_cost
                else:
                    # Partial batch sale
                    shares_queue[0]['quantity'] = batch_qty - shares_to_sell
                    shares_queue[0]['fees'] = batch_fees_per_share * (batch_qty - shares_to_sell)

                    partial_cost = (shares_to_sell * batch_price) + (batch_fees_per_share * shares_to_sell)
                    total_shares -= shares_to_sell
                    total_cost -= partial_cost
                    sell_cost_basis += partial_cost
                    shares_to_sell = 0

            # Calculate realized gain/loss for this sell
            realized_gain_loss += (sell_proceeds - sell_cost_basis)

        elif txn.type == 'DIVIDEND':
            # Dividends don't affect share count or cost basis
            # But they do affect realized gains (cash received)
            dividend_amount = Decimal(str(txn.quantity)) * price
            realized_gain_loss += dividend_amount

        elif txn.type == 'SPLIT':
            # Stock split: adjust all batches in queue
            split_ratio = Decimal(str(txn.price_per_share))  # e.g., 2.0 for 2-for-1 split

            for batch in shares_queue:
                new_quantity = int(batch['quantity'] * split_ratio)
                batch['price_per_share'] = batch['price_per_share'] / split_ratio
                batch['quantity'] = new_quantity

            total_shares = int(total_shares * split_ratio)
            # total_cost remains the same (splits don't change total investment)

    # Calculate average cost basis
    avg_cost_basis = (total_cost / Decimal(str(total_shares))) if total_shares > 0 else Decimal('0.00')

    return (
        total_shares,
        avg_cost_basis,
        total_cost,
        realized_gain_loss,
        first_purchase_date
    )


def update_portfolio_position(transaction):
    """
    Update or create PortfolioPosition after a new transaction.
    This should be called after every transaction insert/update/delete.
    Skipped for DEPOSIT/WITHDRAWAL transactions (no company).

    Args:
        transaction: Transaction object that was just created/modified
    """
    if transaction.type in ('DEPOSIT', 'WITHDRAWAL'):
        return None
    update_portfolio_position_for_company(transaction.company_id, transaction.user_id, transaction.date)


def update_portfolio_position_for_company(company_id, user_id, last_transaction_date=None):
    """
    Update or create PortfolioPosition for a specific company/user combination.
    More efficient for bulk operations where you already have company_id and user_id.

    Args:
        company_id: Company ID to update
        user_id: User ID
        last_transaction_date: Optional last transaction date (will query if not provided)
    """
    # Recalculate position from scratch using FIFO
    total_shares, avg_cost, total_cost, realized_gl, first_date = calculate_fifo_cost_basis(
        company_id,
        user_id
    )

    # Find or create position
    position = PortfolioPosition.query.filter_by(
        user_id=user_id,
        company_id=company_id
    ).first()

    if not position:
        position = PortfolioPosition(
            user_id=user_id,
            company_id=company_id
        )
        db.session.add(position)

    # Get last transaction date if not provided
    if last_transaction_date is None:
        last_txn = Transaction.query.filter_by(
            user_id=user_id,
            company_id=company_id
        ).order_by(Transaction.date.desc()).first()
        last_transaction_date = last_txn.date if last_txn else None

    # Set position currency from company's reporting currency or detect from ticker
    company = Company.query.get(company_id)
    if company:
        from app.services.currency_service import CurrencyService
        if company.reporting_currency:
            position.currency = company.reporting_currency
        elif company.ticker_symbol:
            position.currency = CurrencyService.detect_currency_from_ticker(company.ticker_symbol)

    # Update position data (FIFO results are now in user's base currency)
    position.total_shares = total_shares
    position.average_cost_basis = avg_cost
    position.total_cost = total_cost
    position.average_cost_basis_base = avg_cost
    position.total_cost_base = total_cost
    position.realized_gain_loss = realized_gl
    position.first_purchase_date = first_date
    position.last_transaction_date = last_transaction_date
    position.is_active = (total_shares > 0)

    # Update company's is_in_portfolio flag
    if company:
        if total_shares > 0:
            company.is_in_portfolio = True
        else:
            # Check if user has any other positions in this company
            other_positions = PortfolioPosition.query.filter(
                PortfolioPosition.user_id == user_id,
                PortfolioPosition.company_id == company_id,
            PortfolioPosition.id != position.id if position.id else True,
            PortfolioPosition.is_active == True
        ).count()

            if other_positions == 0:
                company.is_in_portfolio = False

    return position
