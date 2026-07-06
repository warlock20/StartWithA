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

"""remove weekly_review table and spaced repetition fields

Revision ID: remove_weekly_review
Revises: 11a12cc485b5
Create Date: 2026-06-20

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'remove_weekly_review'
down_revision = '11a12cc485b5'
branch_labels = None
depends_on = None


def upgrade():
    # Drop spaced repetition columns from learning_note
    op.drop_column('learning_note', 'next_review_date')
    op.drop_column('learning_note', 'review_interval_days')

    # Drop the weekly_review table
    op.drop_table('weekly_review')


def downgrade():
    # Recreate weekly_review table
    op.create_table(
        'weekly_review',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('week_start', sa.Date(), nullable=False),
        sa.Column('week_end', sa.Date(), nullable=False),
        sa.Column('ideas_captured', sa.Integer(), nullable=True),
        sa.Column('ideas_killed', sa.Integer(), nullable=True),
        sa.Column('research_hours', sa.Float(), nullable=True),
        sa.Column('decisions_made', sa.Integer(), nullable=True),
        sa.Column('biggest_win', sa.Text(), nullable=True),
        sa.Column('biggest_challenge', sa.Text(), nullable=True),
        sa.Column('key_learnings', sa.JSON(), nullable=True),
        sa.Column('market_thoughts', sa.Text(), nullable=True),
        sa.Column('opportunities_identified', sa.JSON(), nullable=True),
        sa.Column('risks_identified', sa.JSON(), nullable=True),
        sa.Column('next_week_priorities', sa.JSON(), nullable=True),
        sa.Column('companies_to_research', sa.JSON(), nullable=True),
        sa.Column('last_week_goals_achieved', sa.JSON(), nullable=True),
        sa.Column('goals_completion_rate', sa.Integer(), nullable=True),
        sa.Column('confidence_level', sa.Integer(), nullable=True),
        sa.Column('market_sentiment', sa.String(length=50), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # Re-add spaced repetition columns to learning_note
    op.add_column('learning_note', sa.Column('next_review_date', sa.Date(), nullable=True))
    op.add_column('learning_note', sa.Column('review_interval_days', sa.Integer(), nullable=True))
