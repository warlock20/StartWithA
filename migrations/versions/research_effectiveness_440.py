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

"""History columns and dismissals for research effectiveness (issue #440)

Revision ID: research_effectiveness_440
Revises: research_outcome_is_received_451
Create Date: 2026-11-25

checklist_answer.verdict_at is when the verdict last changed, journal_entry.archived_at
is when the entry was archived. Existing rows are backfilled from answered_at and
updated_at, the best dates on record.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'research_effectiveness_440'
down_revision = 'research_outcome_is_received_451'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('checklist_answer', sa.Column('verdict_at', sa.DateTime(), nullable=True))
    op.add_column('journal_entry', sa.Column('archived_at', sa.DateTime(), nullable=True))
    op.create_table(
        'research_effectiveness_dismissal',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('finding_key', sa.String(length=120), nullable=False),
        sa.Column('counts', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'finding_key', name='uq_research_effectiveness_dismissal_user_key'),
    )
    op.create_index(op.f('ix_research_effectiveness_dismissal_user_id'),
                    'research_effectiveness_dismissal', ['user_id'])
    op.execute("UPDATE checklist_answer SET verdict_at = answered_at "
               "WHERE satisfaction_status IS NOT NULL AND verdict_at IS NULL")
    op.execute("UPDATE journal_entry SET archived_at = updated_at "
               "WHERE is_archived AND archived_at IS NULL")


def downgrade():
    op.drop_index(op.f('ix_research_effectiveness_dismissal_user_id'),
                  table_name='research_effectiveness_dismissal')
    op.drop_table('research_effectiveness_dismissal')
    op.drop_column('journal_entry', 'archived_at')
    op.drop_column('checklist_answer', 'verdict_at')
