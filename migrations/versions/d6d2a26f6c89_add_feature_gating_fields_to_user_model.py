"""Add feature gating fields to User model

Revision ID: d6d2a26f6c89
Revises: d7532d12cd05
Create Date: 2026-04-24 18:03:13.372174

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd6d2a26f6c89'
down_revision = 'd7532d12cd05'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('show_advanced_features', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('unlocked_features', sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('unlocked_features')
        batch_op.drop_column('show_advanced_features')
