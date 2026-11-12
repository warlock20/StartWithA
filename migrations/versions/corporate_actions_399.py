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

"""corporate actions: corporate_action table and transaction leg columns

Revision ID: corporate_actions_399
Revises: kill_criterion_set_null_370
Create Date: 2026-11-09
"""
from alembic import op
import sqlalchemy as sa


revision = 'corporate_actions_399'
down_revision = 'kill_criterion_set_null_370'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'corporate_action',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('action_type', sa.String(length=20), nullable=False),
        sa.Column('effective_date', sa.Date(), nullable=False),
        sa.Column('source_company_id', sa.Integer(), nullable=False),
        sa.Column('target_company_id', sa.Integer(), nullable=True),
        sa.Column('ratio', sa.Numeric(12, 6), nullable=True),
        sa.Column('cost_allocation_pct', sa.Numeric(6, 3), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.ForeignKeyConstraint(['source_company_id'], ['company.id']),
        sa.ForeignKeyConstraint(['target_company_id'], ['company.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_corporate_action_user_id', 'corporate_action', ['user_id'])
    op.create_index('ix_corporate_action_effective_date', 'corporate_action', ['effective_date'])

    op.add_column('transaction', sa.Column('corporate_action_id', sa.Integer(), nullable=True))
    op.add_column('transaction', sa.Column('corporate_value_base', sa.Numeric(14, 2), nullable=True))
    op.create_foreign_key('fk_transaction_corporate_action', 'transaction', 'corporate_action',
                          ['corporate_action_id'], ['id'], ondelete='CASCADE')
    op.create_index('ix_transaction_corporate_action_id', 'transaction', ['corporate_action_id'])


def downgrade():
    """
    Drops the corporate_action table and the transaction columns, but NOT the leg rows:
    MERGER_OUT/MERGER_IN/SPINOFF_*/STOCK_DIVIDEND transactions stay in the table and the
    old code ignores those types, so merged-away and spun-off positions would reopen.
    Delete the corporate actions in the app (or those rows) before downgrading.
    """
    op.drop_index('ix_transaction_corporate_action_id', table_name='transaction')
    op.drop_constraint('fk_transaction_corporate_action', 'transaction', type_='foreignkey')
    op.drop_column('transaction', 'corporate_value_base')
    op.drop_column('transaction', 'corporate_action_id')
    op.drop_index('ix_corporate_action_effective_date', table_name='corporate_action')
    op.drop_index('ix_corporate_action_user_id', table_name='corporate_action')
    op.drop_table('corporate_action')
