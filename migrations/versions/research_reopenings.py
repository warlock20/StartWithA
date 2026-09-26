# StartWithA
# Copyright (C) 2024-2026 Kiran Mathews
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""research reopenings

Reopening a rejected company clears the fields that recorded the rejection.
This table holds the snapshot taken just before that, so the reason a company
was passed on survives the decision to look at it again.

Revision ID: research_reopenings
Revises: add_agenda_config
Create Date: 2026-09-18

"""
from alembic import op
import sqlalchemy as sa


revision = 'research_reopenings'
down_revision = 'add_agenda_config'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'research_reopenings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=True),
        sa.Column('idea_id', sa.Integer(), nullable=True),
        sa.Column('prior_stage', sa.String(length=20), nullable=False),
        sa.Column('prior_reason', sa.Text(), nullable=True),
        sa.Column('prior_notes', sa.Text(), nullable=True),
        sa.Column('prior_killed_at', sa.DateTime(), nullable=True),
        sa.Column('what_changed', sa.Text(), nullable=True),
        sa.Column('reopened_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.ForeignKeyConstraint(['company_id'], ['company.id']),
        sa.ForeignKeyConstraint(['project_id'], ['research_project.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['idea_id'], ['idea_pipeline.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_research_reopenings_user_id', 'research_reopenings', ['user_id'])
    op.create_index('ix_research_reopenings_company_id', 'research_reopenings', ['company_id'])


def downgrade():
    op.drop_index('ix_research_reopenings_company_id', table_name='research_reopenings')
    op.drop_index('ix_research_reopenings_user_id', table_name='research_reopenings')
    op.drop_table('research_reopenings')
