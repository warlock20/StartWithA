# Investment Checklist Platform
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

"""drop learning_path table

Revision ID: 11a12cc485b5
Revises: add_watchlist_reason
Create Date: 2026-06-14 21:12:34.179672

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '11a12cc485b5'
down_revision = 'add_watchlist_reason'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table('learning_path')


def downgrade():
    op.create_table(
        'learning_path',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('skill_area', sa.String(length=100), nullable=True),
        sa.Column('total_steps', sa.Integer(), nullable=True),
        sa.Column('completed_steps', sa.Integer(), nullable=True),
        sa.Column('learning_resources', sa.JSON(), nullable=True),
        sa.Column('practice_exercises', sa.JSON(), nullable=True),
        sa.Column('milestones', sa.JSON(), nullable=True),
        sa.Column('current_step', sa.Integer(), nullable=True),
        sa.Column('progress_notes', sa.JSON(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('target_completion', sa.Date(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
