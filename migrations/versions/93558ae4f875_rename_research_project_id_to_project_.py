"""Rename research_project_id to project_id in work_session and research_outcome, add unique constraint on research_project

Revision ID: 93558ae4f875
Revises: 4761422fc789
Create Date: 2026-02-22 19:14:09.928436

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '93558ae4f875'
down_revision = '4761422fc789'
branch_labels = None
depends_on = None


def upgrade():
    # Rename columns (preserves data)
    op.alter_column('work_session', 'research_project_id', new_column_name='project_id')
    op.alter_column('research_outcome', 'research_project_id', new_column_name='project_id')

    # Add unique constraint
    op.create_unique_constraint('uq_research_project_user_company', 'research_project', ['user_id', 'company_id'])


def downgrade():
    op.drop_constraint('uq_research_project_user_company', 'research_project', type_='unique')

    op.alter_column('research_outcome', 'project_id', new_column_name='research_project_id')
    op.alter_column('work_session', 'project_id', new_column_name='research_project_id')
