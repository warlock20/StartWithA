"""Add description column to DestinationCheckpoint

Revision ID: 8eefeadbe133
Revises: 1245d6c3dbc3
Create Date: 2026-03-27 20:41:02.780523

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8eefeadbe133'
down_revision = '1245d6c3dbc3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('destination_checkpoint', schema=None) as batch_op:
        batch_op.add_column(sa.Column('description', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('destination_checkpoint', schema=None) as batch_op:
        batch_op.drop_column('description')
