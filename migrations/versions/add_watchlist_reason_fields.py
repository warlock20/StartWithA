"""Add watch_reason and watch_notes to ResearchProject

Revision ID: add_watchlist_reason
Revises: 6dff42f40a10
Create Date: 2026-05-26

Adds two columns to support watchlisting active research projects
with a structured reason:
- watch_reason: enum-like string for categorised watch reasons
- watch_notes: free-text notes explaining why the project is on the watchlist
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_watchlist_reason'
down_revision = '6dff42f40a10'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('research_project', sa.Column('watch_reason', sa.String(length=50), nullable=True))
    op.add_column('research_project', sa.Column('watch_notes', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('research_project', 'watch_notes')
    op.drop_column('research_project', 'watch_reason')
