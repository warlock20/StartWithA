"""Add status and tracking fields to SectorAnalysis

Revision ID: add_sector_status_tracking
Revises: simplify_research_company
Create Date: 2025-10-06

This migration adds research progress tracking fields to SectorAnalysis:
1. status field (active/archived)
2. total_time_spent for tracking research time in seconds
3. archived_at timestamp for when research was archived
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_sector_status_tracking'
down_revision = 'simplify_research_company'
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to sector_analysis table
    op.add_column('sector_analysis', sa.Column('status', sa.String(length=20), nullable=False, server_default='active'))
    op.add_column('sector_analysis', sa.Column('total_time_spent', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('sector_analysis', sa.Column('archived_at', sa.DateTime(), nullable=True))


def downgrade():
    # Remove columns if rolling back
    op.drop_column('sector_analysis', 'archived_at')
    op.drop_column('sector_analysis', 'total_time_spent')
    op.drop_column('sector_analysis', 'status')
