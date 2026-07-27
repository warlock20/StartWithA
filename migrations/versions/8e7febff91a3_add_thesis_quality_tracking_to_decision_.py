"""add_thesis_quality_tracking_to_decision_journal

Revision ID: 8e7febff91a3
Revises: f28d03104087
Create Date: 2025-11-13 12:20:37.623144

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8e7febff91a3'
down_revision = 'f28d03104087'
branch_labels = None
depends_on = None


def upgrade():
    # Add thesis quality tracking fields to decision_journal table
    op.add_column('decision_journal', sa.Column('thesis_depth', sa.String(length=50), nullable=True))
    op.add_column('decision_journal', sa.Column('thesis_word_count', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('decision_journal', sa.Column('non_research_source', sa.String(length=100), nullable=True))


def downgrade():
    # Remove thesis quality tracking fields
    op.drop_column('decision_journal', 'non_research_source')
    op.drop_column('decision_journal', 'thesis_word_count')
    op.drop_column('decision_journal', 'thesis_depth')
