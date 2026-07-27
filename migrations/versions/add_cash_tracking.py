"""Add cash tracking support

Revision ID: ce7a4450f981
Revises: 7abb4b77d5d3
Create Date: 2026-03-18 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ce7a4450f981'
down_revision = '7abb4b77d5d3'
branch_labels = None
depends_on = None


def upgrade():
    # Transaction table: make company_id and quantity nullable for DEPOSIT/WITHDRAWAL
    op.alter_column('transaction', 'company_id', existing_type=sa.Integer(), nullable=True)
    op.alter_column('transaction', 'quantity', existing_type=sa.Integer(), nullable=True)
    op.alter_column('transaction', 'price_per_share', existing_type=sa.Numeric(10, 2), nullable=True)

    # Transaction table: add cash amount columns
    op.add_column('transaction', sa.Column('cash_amount', sa.Numeric(12, 2), nullable=True))
    op.add_column('transaction', sa.Column('cash_amount_base', sa.Numeric(12, 2), nullable=True))

    # User table: add cash balance and setup flag
    op.add_column('user', sa.Column('cash_balance', sa.Numeric(12, 2), nullable=False, server_default='0'))
    op.add_column('user', sa.Column('cash_setup_complete', sa.Boolean(), nullable=False, server_default='false'))


def downgrade():
    # User table: remove cash columns
    op.drop_column('user', 'cash_setup_complete')
    op.drop_column('user', 'cash_balance')

    # Transaction table: remove cash columns
    op.drop_column('transaction', 'cash_amount_base')
    op.drop_column('transaction', 'cash_amount')

    # Transaction table: revert nullable changes
    op.alter_column('transaction', 'price_per_share', existing_type=sa.Numeric(10, 2), nullable=False)
    op.alter_column('transaction', 'quantity', existing_type=sa.Integer(), nullable=False)
    op.alter_column('transaction', 'company_id', existing_type=sa.Integer(), nullable=False)
