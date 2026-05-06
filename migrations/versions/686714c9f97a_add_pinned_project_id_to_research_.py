"""Add pinned_project_id to research_settings

Revision ID: 686714c9f97a
Revises: dab0178b5a00
Create Date: 2026-05-04 19:43:23.034632

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '686714c9f97a'
down_revision = 'dab0178b5a00'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('research_settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('pinned_project_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_research_settings_pinned_project', 'research_project', ['pinned_project_id'], ['id'], ondelete='SET NULL')


def downgrade():
    with op.batch_alter_table('research_settings', schema=None) as batch_op:
        batch_op.drop_constraint('fk_research_settings_pinned_project', type_='foreignkey')
        batch_op.drop_column('pinned_project_id')
