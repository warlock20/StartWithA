"""add_sector_research_sections_and_sources_tables

Revision ID: deece4cc6cc9
Revises: 40cbcec1c0f0
Create Date: 2025-10-02 21:43:00.405769

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'deece4cc6cc9'
down_revision = '40cbcec1c0f0'
branch_labels = None
depends_on = None


def upgrade():
    # Create sector_research_section table
    op.create_table('sector_research_section',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sector_analysis_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('icon', sa.String(length=50), nullable=True),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('section_type', sa.String(length=50), nullable=True, server_default='custom'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('is_visible', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('is_locked', sa.Boolean(), nullable=True, server_default='false'),
        sa.ForeignKeyConstraint(['sector_analysis_id'], ['sector_analysis.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sector_research_section_sector_analysis_id'), 'sector_research_section', ['sector_analysis_id'], unique=False)
    op.create_index(op.f('ix_sector_research_section_display_order'), 'sector_research_section', ['display_order'], unique=False)

    # Create sector_research_source table
    op.create_table('sector_research_source',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sector_analysis_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('url', sa.String(length=1000), nullable=True),
        sa.Column('source_type', sa.String(length=50), nullable=False, server_default='article'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('key_takeaways', sa.Text(), nullable=True),
        sa.Column('author', sa.String(length=200), nullable=True),
        sa.Column('publisher', sa.String(length=200), nullable=True),
        sa.Column('published_date', sa.Date(), nullable=True),
        sa.Column('tags', sa.String(length=500), nullable=True),
        sa.Column('relevance_score', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('accessed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['sector_analysis_id'], ['sector_analysis.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sector_research_source_sector_analysis_id'), 'sector_research_source', ['sector_analysis_id'], unique=False)
    op.create_index(op.f('ix_sector_research_source_source_type'), 'sector_research_source', ['source_type'], unique=False)


def downgrade():
    # Drop sector_research_source table
    op.drop_index(op.f('ix_sector_research_source_source_type'), table_name='sector_research_source')
    op.drop_index(op.f('ix_sector_research_source_sector_analysis_id'), table_name='sector_research_source')
    op.drop_table('sector_research_source')

    # Drop sector_research_section table
    op.drop_index(op.f('ix_sector_research_section_display_order'), table_name='sector_research_section')
    op.drop_index(op.f('ix_sector_research_section_sector_analysis_id'), table_name='sector_research_section')
    op.drop_table('sector_research_section')
