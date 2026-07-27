"""Drop old company_document, company_article, research_attachment tables

Revision ID: aa667ebfb53d
Revises: 1ddadee7884f
Create Date: 2026-05-06 08:04:29.184392

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'aa667ebfb53d'
down_revision = '1ddadee7884f'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table('research_attachment')
    op.drop_table('company_article')
    op.drop_table('company_document')


def downgrade():
    # Recreate company_document
    op.create_table(
        'company_document',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('original_filename', sa.String(255), nullable=False),
        sa.Column('stored_filename', sa.String(300), nullable=False),
        sa.Column('document_group', sa.String(100), nullable=False),
        sa.Column('document_title', sa.String(255), nullable=True),
        sa.Column('document_date', sa.Date(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['company_id'], ['company.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.UniqueConstraint('stored_filename', name='company_document_stored_filename_key'),
    )
    op.create_index('ix_company_document_document_group', 'company_document', ['document_group'])

    # Recreate company_article
    op.create_table(
        'company_article',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(300), nullable=False),
        sa.Column('url', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('source_name', sa.String(100), nullable=True),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('fetched_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['company_id'], ['company.id']),
    )
    op.create_index('ix_company_article_published_at', 'company_article', ['published_at'])

    # Recreate research_attachment
    op.create_table(
        'research_attachment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('step_index', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('original_filename', sa.String(255), nullable=False),
        sa.Column('stored_filename', sa.String(300), nullable=False),
        sa.Column('file_type', sa.String(50), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['research_project.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.UniqueConstraint('stored_filename', name='research_attachment_stored_filename_key'),
    )
