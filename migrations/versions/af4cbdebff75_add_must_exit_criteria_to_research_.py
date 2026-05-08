"""Add must_exit_criteria to research_project

Revision ID: af4cbdebff75
Revises: aa667ebfb53d
Create Date: 2026-05-08 18:30:17.865422

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'af4cbdebff75'
down_revision = 'aa667ebfb53d'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('research_project', schema=None) as batch_op:
        batch_op.add_column(sa.Column('must_exit_criteria', sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table('research_project', schema=None) as batch_op:
        batch_op.drop_column('must_exit_criteria')
