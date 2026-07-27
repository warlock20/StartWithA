"""Add journey_notes to company

Revision ID: d7532d12cd05
Revises: 5c76573c44e8
Create Date: 2026-04-14 14:45:31.140189

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd7532d12cd05'
down_revision = '5c76573c44e8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('company', schema=None) as batch_op:
        batch_op.add_column(sa.Column('journey_notes', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('journey_notes_updated_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('company', schema=None) as batch_op:
        batch_op.drop_column('journey_notes_updated_at')
        batch_op.drop_column('journey_notes')
