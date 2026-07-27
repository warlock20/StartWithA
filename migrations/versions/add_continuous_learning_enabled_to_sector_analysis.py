"""Add continuous_learning_enabled field to SectorAnalysis

Revision ID: add_continuous_learning_tracking
Revises: add_knowledge_library
Create Date: 2025-11-29

This migration adds continuous learning tracking toggle to SectorAnalysis:
- continuous_learning_enabled: Boolean field to enable/disable sector in Learning Center
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_continuous_learning_tracking'
down_revision = 'add_knowledge_library'
branch_labels = None
depends_on = None


def upgrade():
    # Add continuous_learning_enabled column to sector_analysis table
    op.add_column('sector_analysis', sa.Column('continuous_learning_enabled', sa.Boolean(), nullable=False, server_default='0'))


def downgrade():
    # Remove column if rolling back
    op.drop_column('sector_analysis', 'continuous_learning_enabled')
