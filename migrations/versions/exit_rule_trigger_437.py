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

"""Exit-rule trigger episodes (issue #437)

Revision ID: exit_rule_trigger_437
Revises: exit_watch_search_437
Create Date: 2026-11-22

One row per episode of a must-exit rule going from intact to at_risk or
triggered, with the user's response (sold, held, ignored).
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'exit_rule_trigger_437'
down_revision = 'exit_watch_search_437'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'exit_rule_trigger',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('rule_id', sa.Integer(), nullable=False),
        sa.Column('opened_at', sa.DateTime(), nullable=False),
        sa.Column('opening_insight_id', sa.Integer(), nullable=True),
        sa.Column('worst_status', sa.String(length=10), nullable=False),
        sa.Column('current_status', sa.String(length=10), nullable=False),
        sa.Column('price_at_open', sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column('price_currency', sa.String(length=3), nullable=True),
        sa.Column('response', sa.String(length=10), nullable=False, server_default='pending'),
        sa.Column('responded_at', sa.DateTime(), nullable=True),
        sa.Column('hold_entry_id', sa.Integer(), nullable=True),
        sa.Column('held_at', sa.DateTime(), nullable=True),
        sa.Column('ignored_at', sa.DateTime(), nullable=True),
        sa.Column('sold_pct', sa.Float(), nullable=True),
        sa.Column('sold_after_hold', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('realerted_at', sa.DateTime(), nullable=True),
        sa.Column('realert_reason', sa.String(length=12), nullable=True),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('close_reason', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['company_id'], ['company.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['rule_id'], ['journal_entry.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['opening_insight_id'], ['ai_insight.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['hold_entry_id'], ['journal_entry.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_exit_rule_trigger_user_closed', 'exit_rule_trigger', ['user_id', 'closed_at'])
    op.create_index('ix_exit_rule_trigger_rule_closed', 'exit_rule_trigger', ['rule_id', 'closed_at'])
    op.create_index('uq_exit_rule_trigger_open_rule', 'exit_rule_trigger', ['rule_id'], unique=True,
                    postgresql_where=sa.text('closed_at IS NULL'))


def downgrade():
    op.drop_index('uq_exit_rule_trigger_open_rule', table_name='exit_rule_trigger')
    op.drop_index('ix_exit_rule_trigger_rule_closed', table_name='exit_rule_trigger')
    op.drop_index('ix_exit_rule_trigger_user_closed', table_name='exit_rule_trigger')
    op.drop_table('exit_rule_trigger')
