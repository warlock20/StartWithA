"""Rename subscription tier 'free' to 'amateur'

Revision ID: rename_free_to_amateur
Revises: add_total_dividends
Create Date: 2026-07-09

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'rename_free_to_amateur'
down_revision = 'add_total_dividends'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        UPDATE "user"
        SET subscription_tier = 'amateur'
        WHERE subscription_tier = 'free'
    """)


def downgrade():
    op.execute("""
        UPDATE "user"
        SET subscription_tier = 'free'
        WHERE subscription_tier = 'amateur'
    """)
