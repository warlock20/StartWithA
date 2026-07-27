"""Add knowledge library fields to learning_note

Revision ID: add_knowledge_library
Revises: multi_currency_001
Create Date: 2025-11-26 07:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_knowledge_library'
down_revision = 'multi_currency_001'
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to learning_note table
    op.add_column('learning_note', sa.Column('source_url', sa.String(length=500), nullable=True))
    op.add_column('learning_note', sa.Column('source_author', sa.String(length=200), nullable=True))
    op.add_column('learning_note', sa.Column('source_date', sa.Date(), nullable=True))
    op.add_column('learning_note', sa.Column('knowledge_type', sa.String(length=50), nullable=True))
    op.add_column('learning_note', sa.Column('topic_tags', sa.JSON(), nullable=True))
    op.add_column('learning_note', sa.Column('investor_tags', sa.JSON(), nullable=True))
    op.add_column('learning_note', sa.Column('is_favorite', sa.Boolean(), nullable=True, server_default='false'))


def downgrade():
    # Remove added columns
    op.drop_column('learning_note', 'is_favorite')
    op.drop_column('learning_note', 'investor_tags')
    op.drop_column('learning_note', 'topic_tags')
    op.drop_column('learning_note', 'knowledge_type')
    op.drop_column('learning_note', 'source_date')
    op.drop_column('learning_note', 'source_author')
    op.drop_column('learning_note', 'source_url')
