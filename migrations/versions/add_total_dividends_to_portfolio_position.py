"""Add total_dividends to portfolio_position

Revision ID: add_total_dividends
Revises: remove_weekly_review
Create Date: 2026-07-07 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_total_dividends'
down_revision = 'remove_weekly_review'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('portfolio_position', sa.Column(
        'total_dividends', sa.Numeric(12, 2), nullable=False, server_default='0.00'
    ))


def downgrade():
    op.drop_column('portfolio_position', 'total_dividends')
