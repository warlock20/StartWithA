"""Add missing prompt_version string column to prompt_usage_log

The model declared `prompt_version` twice — once as a String column, then again
as a relationship — so the column was shadowed away before Alembic ever saw it
and the table was created without it. Every log_prompt_usage() call therefore
failed with "'str' object has no attribute '_sa_instance_state'". The
relationship is now named `version_record`; this restores the column.

Revision ID: a4e1c9b7d2f3
Revises: c85080497f69
Create Date: 2026-07-31 16:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a4e1c9b7d2f3'
down_revision = 'c85080497f69'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('prompt_usage_log', schema=None) as batch_op:
        batch_op.add_column(sa.Column('prompt_version', sa.String(length=20), nullable=True))


def downgrade():
    with op.batch_alter_table('prompt_usage_log', schema=None) as batch_op:
        batch_op.drop_column('prompt_version')
