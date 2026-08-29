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

"""add isin to company and market_sweep_company

ISIN is the only value that identifies a security unambiguously across the
market sweeps and a user's own companies. Ticker cannot: sweeps carry local
exchange codes (ABBN, 1U1) while Company carries Yahoo symbols (ABBN.SW).
Name cannot: "Bosch Limited" (India) and "Bosch Fren Sistemleri" (Turkey)
normalise to the same string and are unrelated companies.

Both columns are nullable and stay that way. Roughly 8,600 of 8,940 sweep rows
have no ISIN today and may never have one; a blank is a supported state, not a
defect.

Revision ID: add_isin_identity
Revises: a4e1c9b7d2f3
Create Date: 2026-08-28

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_isin_identity'
down_revision = 'a4e1c9b7d2f3'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('company', sa.Column('isin', sa.String(length=12), nullable=True))
    op.create_index('ix_company_isin', 'company', ['isin'])
    op.create_unique_constraint('uq_company_user_isin', 'company', ['user_id', 'isin'])

    op.add_column('market_sweep_company',
                  sa.Column('isin', sa.String(length=12), nullable=True))
    op.create_index('ix_market_sweep_company_isin', 'market_sweep_company', ['isin'])


def downgrade():
    op.drop_index('ix_market_sweep_company_isin', table_name='market_sweep_company')
    op.drop_column('market_sweep_company', 'isin')

    op.drop_constraint('uq_company_user_isin', 'company', type_='unique')
    op.drop_index('ix_company_isin', table_name='company')
    op.drop_column('company', 'isin')
