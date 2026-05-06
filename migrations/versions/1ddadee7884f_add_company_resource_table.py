"""add company_resource table

Revision ID: 1ddadee7884f
Revises: 686714c9f97a
Create Date: 2026-05-05 18:17:17.694815

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1ddadee7884f'
down_revision = '686714c9f97a'
branch_labels = None
depends_on = None


def upgrade():
    # Create the unified company_resource table
    op.create_table(
        'company_resource',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('resource_type', sa.String(20), nullable=False),
        sa.Column('title', sa.String(300), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('original_filename', sa.String(255), nullable=True),
        sa.Column('stored_filename', sa.String(300), nullable=True),
        sa.Column('file_type', sa.String(50), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('url', sa.String(500), nullable=True),
        sa.Column('source_name', sa.String(100), nullable=True),
        sa.Column('research_project_id', sa.Integer(), nullable=True),
        sa.Column('research_step_index', sa.Integer(), nullable=True),
        sa.Column('resource_date', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['company.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.ForeignKeyConstraint(['research_project_id'], ['research_project.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('stored_filename'),
    )
    op.create_index('ix_company_resource_company_id', 'company_resource', ['company_id'])
    op.create_index('ix_company_resource_resource_type', 'company_resource', ['resource_type'])
    op.create_index('ix_company_resource_category', 'company_resource', ['category'])
    op.create_index('ix_company_resource_research_project_id', 'company_resource', ['research_project_id'])

    # Migrate data from CompanyDocument
    op.execute("""
        INSERT INTO company_resource
            (company_id, user_id, resource_type, title, description, category,
             original_filename, stored_filename, file_type, resource_date, created_at)
        SELECT
            company_id, user_id, 'file',
            COALESCE(document_title, original_filename),
            description, document_group,
            original_filename, stored_filename,
            CASE
                WHEN LOWER(original_filename) LIKE '%.pdf' THEN 'pdf'
                WHEN LOWER(original_filename) LIKE '%.txt' THEN 'txt'
                ELSE NULL
            END,
            document_date, uploaded_at
        FROM company_document
    """)

    # Migrate data from CompanyArticle (user_id derived from company.user_id)
    op.execute("""
        INSERT INTO company_resource
            (company_id, user_id, resource_type, title, description,
             url, source_name, category, created_at)
        SELECT
            ca.company_id, c.user_id, 'link',
            ca.title, ca.description,
            ca.url, ca.source_name, ca.source_name,
            ca.fetched_at
        FROM company_article ca
        JOIN company c ON ca.company_id = c.id
    """)

    # Migrate data from ResearchAttachment (company_id derived from research_project.company_id)
    op.execute("""
        INSERT INTO company_resource
            (company_id, user_id, resource_type, title,
             original_filename, stored_filename, file_type, file_size,
             research_project_id, research_step_index, created_at)
        SELECT
            rp.company_id, ra.user_id, 'file',
            ra.title,
            ra.original_filename, ra.stored_filename, ra.file_type, ra.file_size,
            ra.project_id, ra.step_index, ra.uploaded_at
        FROM research_attachment ra
        JOIN research_project rp ON ra.project_id = rp.id
    """)


def downgrade():
    op.drop_index('ix_company_resource_research_project_id', 'company_resource')
    op.drop_index('ix_company_resource_category', 'company_resource')
    op.drop_index('ix_company_resource_resource_type', 'company_resource')
    op.drop_index('ix_company_resource_company_id', 'company_resource')
    op.drop_table('company_resource')
