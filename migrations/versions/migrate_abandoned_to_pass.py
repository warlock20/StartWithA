"""Migrate abandoned projects to pass decision

This migration converts all research projects with status='abandoned'
to status='completed' and decision='pass'. This simplifies the data model
to use decision='pass' as the single source of truth for the Too Hard Basket.

Revision ID: migrate_abandoned_pass
Revises: 7bd7d4065ba9
Create Date: 2026-01-19

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'migrate_abandoned_pass'
down_revision = '7bd7d4065ba9'
branch_labels = None
depends_on = None


def upgrade():
    # Update all research projects with status='abandoned' to use the new model
    # Set status='completed' and decision='pass' for consistent data
    op.execute("""
        UPDATE research_project
        SET status = 'completed',
            decision = 'pass',
            decision_date = COALESCE(abandoned_at, NOW())
        WHERE status = 'abandoned'
    """)


def downgrade():
    # Revert: set status back to 'abandoned' for projects that were mid-research passes
    # We can identify them by having too_hard_reason set
    op.execute("""
        UPDATE research_project
        SET status = 'abandoned',
            decision = NULL
        WHERE decision = 'pass' AND too_hard_reason IS NOT NULL
    """)
