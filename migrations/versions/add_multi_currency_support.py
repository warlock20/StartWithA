"""add multi-currency support

Revision ID: multi_currency_001
Revises: de438cfe4dc9
Create Date: 2025-11-18 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'multi_currency_001'
down_revision = 'de438cfe4dc9'  # Latest migration: add position tracking fields
branch_labels = None
depends_on = None


def upgrade():
    """
    Add multi-currency support to portfolio system.

    This migration adds:
    - ExchangeRate table for caching exchange rates
    - Currency fields to Transaction model
    - Currency fields to PortfolioPosition model
    - base_currency field to User model
    """

    # Create exchange_rate table
    op.create_table(
        'exchange_rate',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('from_currency', sa.String(length=3), nullable=False),
        sa.Column('to_currency', sa.String(length=3), nullable=False),
        sa.Column('rate', sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=True),
        sa.Column('fetched_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('from_currency', 'to_currency', 'date', name='uq_currency_pair_date')
    )

    # Create indexes for exchange_rate
    op.create_index('idx_exchange_rate_lookup', 'exchange_rate',
                    ['from_currency', 'to_currency', 'date'])
    op.create_index(op.f('ix_exchange_rate_from_currency'), 'exchange_rate', ['from_currency'])
    op.create_index(op.f('ix_exchange_rate_to_currency'), 'exchange_rate', ['to_currency'])
    op.create_index(op.f('ix_exchange_rate_date'), 'exchange_rate', ['date'])

    # Add currency fields to transaction table
    op.add_column('transaction', sa.Column('currency', sa.String(length=3),
                                           nullable=False, server_default='USD'))
    op.add_column('transaction', sa.Column('price_per_share_base', sa.Numeric(precision=10, scale=2),
                                           nullable=True))
    op.add_column('transaction', sa.Column('fees_base', sa.Numeric(precision=10, scale=2),
                                           nullable=True))
    op.add_column('transaction', sa.Column('exchange_rate', sa.Numeric(precision=10, scale=6),
                                           nullable=True))
    op.add_column('transaction', sa.Column('exchange_rate_date', sa.Date(),
                                           nullable=True))

    # Create index for transaction currency
    op.create_index(op.f('ix_transaction_currency'), 'transaction', ['currency'])

    # Backfill existing transactions with USD and copy prices to base currency fields
    op.execute("""
        UPDATE transaction
        SET
            price_per_share_base = price_per_share,
            fees_base = fees,
            exchange_rate = 1.0,
            exchange_rate_date = date
        WHERE price_per_share_base IS NULL
    """)

    # Add currency fields to portfolio_position table
    op.add_column('portfolio_position', sa.Column('currency', sa.String(length=3),
                                                  nullable=False, server_default='USD'))
    op.add_column('portfolio_position', sa.Column('average_cost_basis_base', sa.Numeric(precision=10, scale=2),
                                                  nullable=True))
    op.add_column('portfolio_position', sa.Column('total_cost_base', sa.Numeric(precision=12, scale=2),
                                                  nullable=True))
    op.add_column('portfolio_position', sa.Column('current_price_base', sa.Numeric(precision=10, scale=2),
                                                  nullable=True))
    op.add_column('portfolio_position', sa.Column('current_value_base', sa.Numeric(precision=12, scale=2),
                                                  nullable=True))
    op.add_column('portfolio_position', sa.Column('current_exchange_rate', sa.Numeric(precision=10, scale=6),
                                                  nullable=True))
    op.add_column('portfolio_position', sa.Column('last_exchange_rate_update', sa.DateTime(),
                                                  nullable=True))
    op.add_column('portfolio_position', sa.Column('currency_gain_loss', sa.Numeric(precision=12, scale=2),
                                                  nullable=False, server_default='0.00'))
    op.add_column('portfolio_position', sa.Column('currency_gain_loss_pct', sa.Numeric(precision=6, scale=2),
                                                  nullable=False, server_default='0.00'))

    # Create index for position currency
    op.create_index(op.f('ix_portfolio_position_currency'), 'portfolio_position', ['currency'])

    # Backfill existing positions with USD and copy values to base currency fields
    op.execute("""
        UPDATE portfolio_position
        SET
            average_cost_basis_base = average_cost_basis,
            total_cost_base = total_cost,
            current_price_base = current_price,
            current_value_base = current_value,
            current_exchange_rate = 1.0
        WHERE average_cost_basis_base IS NULL
    """)

    # Add base_currency to user table
    op.add_column('user', sa.Column('base_currency', sa.String(length=3),
                                    nullable=False, server_default='USD'))
    op.add_column('user', sa.Column('show_original_currency', sa.Boolean(),
                                    nullable=True, server_default='true'))


def downgrade():
    """
    Remove multi-currency support.
    WARNING: This will delete currency-related data!
    """

    # Remove user columns
    op.drop_column('user', 'show_original_currency')
    op.drop_column('user', 'base_currency')

    # Remove portfolio_position columns
    op.drop_index(op.f('ix_portfolio_position_currency'), table_name='portfolio_position')
    op.drop_column('portfolio_position', 'currency_gain_loss_pct')
    op.drop_column('portfolio_position', 'currency_gain_loss')
    op.drop_column('portfolio_position', 'last_exchange_rate_update')
    op.drop_column('portfolio_position', 'current_exchange_rate')
    op.drop_column('portfolio_position', 'current_value_base')
    op.drop_column('portfolio_position', 'current_price_base')
    op.drop_column('portfolio_position', 'total_cost_base')
    op.drop_column('portfolio_position', 'average_cost_basis_base')
    op.drop_column('portfolio_position', 'currency')

    # Remove transaction columns
    op.drop_index(op.f('ix_transaction_currency'), table_name='transaction')
    op.drop_column('transaction', 'exchange_rate_date')
    op.drop_column('transaction', 'exchange_rate')
    op.drop_column('transaction', 'fees_base')
    op.drop_column('transaction', 'price_per_share_base')
    op.drop_column('transaction', 'currency')

    # Drop exchange_rate table
    op.drop_index('idx_exchange_rate_lookup', table_name='exchange_rate')
    op.drop_index(op.f('ix_exchange_rate_date'), table_name='exchange_rate')
    op.drop_index(op.f('ix_exchange_rate_to_currency'), table_name='exchange_rate')
    op.drop_index(op.f('ix_exchange_rate_from_currency'), table_name='exchange_rate')
    op.drop_table('exchange_rate')
