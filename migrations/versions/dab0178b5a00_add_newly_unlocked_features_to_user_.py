"""Add newly_unlocked_features to User model

Revision ID: dab0178b5a00
Revises: d6d2a26f6c89
Create Date: 2026-05-01 07:35:50.757846

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'dab0178b5a00'
down_revision = 'd6d2a26f6c89'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('newly_unlocked_features', sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('newly_unlocked_features')
