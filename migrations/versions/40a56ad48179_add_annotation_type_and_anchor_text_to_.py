"""add annotation_type and anchor_text to document_annotation

Revision ID: 40a56ad48179
Revises: 75469181028d
Create Date: 2026-05-19 14:55:47.144944

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '40a56ad48179'
down_revision = '75469181028d'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('document_annotation', schema=None) as batch_op:
        batch_op.add_column(sa.Column('annotation_type', sa.String(length=20), server_default='pin', nullable=False))
        batch_op.add_column(sa.Column('anchor_text', sa.Text(), nullable=True))
        batch_op.alter_column('x_percent',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=True)
        batch_op.alter_column('y_percent',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=True)


def downgrade():
    with op.batch_alter_table('document_annotation', schema=None) as batch_op:
        batch_op.alter_column('y_percent',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=False)
        batch_op.alter_column('x_percent',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=False)
        batch_op.drop_column('anchor_text')
        batch_op.drop_column('annotation_type')
