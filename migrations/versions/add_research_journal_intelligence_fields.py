"""Add research journal intelligence fields

Revision ID: research_journal_intelligence
Revises: add_dynamic_kill_checklist_features
Create Date: 2024-09-26 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'research_journal_intelligence'
down_revision = 'a1b2c3d4e5f6'  # Points to the dynamic kill checklist migration
branch_labels = None
depends_on = None


def upgrade():
    """Add AI intelligence fields to journal_entry table"""
    with op.batch_alter_table('journal_entry', schema=None) as batch_op:
        # AI Analysis results
        batch_op.add_column(sa.Column('ai_analysis_result', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('ai_analyzed_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('ai_confidence_score', sa.Float(), nullable=True))

        # Intelligent tagging
        batch_op.add_column(sa.Column('ai_suggested_tags', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('ai_themes_extracted', sa.JSON(), nullable=True))

        # Connection tracking
        batch_op.add_column(sa.Column('related_entry_ids', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('contradiction_flags', sa.JSON(), nullable=True))

        # Processing status
        batch_op.add_column(sa.Column('ai_processing_status', sa.String(50), nullable=True))
        # Status values: 'pending', 'processing', 'completed', 'failed', 'skipped'


def downgrade():
    """Remove AI intelligence fields from journal_entry table"""
    with op.batch_alter_table('journal_entry', schema=None) as batch_op:
        batch_op.drop_column('ai_processing_status')
        batch_op.drop_column('contradiction_flags')
        batch_op.drop_column('related_entry_ids')
        batch_op.drop_column('ai_themes_extracted')
        batch_op.drop_column('ai_suggested_tags')
        batch_op.drop_column('ai_confidence_score')
        batch_op.drop_column('ai_analyzed_at')
        batch_op.drop_column('ai_analysis_result')