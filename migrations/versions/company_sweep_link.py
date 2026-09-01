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

"""Link market-sweep rows to per-user companies (issue #330, step 2)

Revision ID: company_sweep_link
Revises: add_isin_identity
Create Date: 2026-08-31 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'company_sweep_link'
down_revision = 'add_isin_identity'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'company_sweep_link',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('sweep_company_id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('origin', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sweep_company_id'], ['market_sweep_company.id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['company_id'], ['company.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'sweep_company_id',
                            name='_user_sweep_company_link_uc'),
    )
    op.create_index('ix_company_sweep_link_user_id', 'company_sweep_link', ['user_id'])
    op.create_index('ix_company_sweep_link_sweep_company_id', 'company_sweep_link',
                    ['sweep_company_id'])
    op.create_index('ix_company_sweep_link_company_id', 'company_sweep_link',
                    ['company_id'])


def downgrade():
    op.drop_table('company_sweep_link')
