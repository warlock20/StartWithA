"""Add key_takeaways to sector_analysis

Revision ID: add_key_takeaways_sector
Revises: dbe738d7c27e
Create Date: 2025-10-09

This migration adds the key_takeaways column to the sector_analysis table
to support the Document View takeaways editor.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_key_takeaways_sector'
down_revision = 'dbe738d7c27e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('sector_analysis', schema=None) as batch_op:
        batch_op.add_column(sa.Column('key_takeaways', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('sector_analysis', schema=None) as batch_op:
        batch_op.drop_column('key_takeaways')
