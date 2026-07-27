"""add document_annotation table

Revision ID: 75469181028d
Revises: standalone_free_research
Create Date: 2026-05-18 19:17:36.556438

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '75469181028d'
down_revision = 'standalone_free_research'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('document_annotation',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('resource_id', sa.Integer(), nullable=False),
    sa.Column('company_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('page_number', sa.Integer(), nullable=False),
    sa.Column('x_percent', sa.Float(), nullable=False),
    sa.Column('y_percent', sa.Float(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('scope', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['company_id'], ['company.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['resource_id'], ['company_resource.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('document_annotation', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_document_annotation_company_id'), ['company_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_document_annotation_resource_id'), ['resource_id'], unique=False)


def downgrade():
    with op.batch_alter_table('document_annotation', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_document_annotation_resource_id'))
        batch_op.drop_index(batch_op.f('ix_document_annotation_company_id'))

    op.drop_table('document_annotation')
