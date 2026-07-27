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

"""unique company ticker per user

Nothing at the database level stopped a user from ending up with two Company
rows for the same ticker, and in practice that happened: one row accumulated
the transactions while an identical twin sat empty beside it, showing up as a
duplicate in every company dropdown.

Application code guards against this on each creation path, but a guard in the
application cannot be relied upon across concurrent requests or future paths.
This makes it impossible.

Revision ID: unique_company_ticker
Revises: 644ee0c924cf
Create Date: 2026-07-21

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'unique_company_ticker'
down_revision = '644ee0c924cf'
branch_labels = None
depends_on = None

CONSTRAINT_NAME = 'uq_company_user_ticker'


def upgrade():
    # Existing duplicates cannot be merged automatically: deciding which copy
    # survives can mean discarding real transaction history, which is not a
    # choice a migration should make unattended. Where they exist, skip the
    # constraint rather than fail -- a blocked deploy helps nobody, and the
    # duplicates are a display annoyance rather than a correctness problem.
    #
    # Databases without duplicates (fresh installs, clean environments) still
    # get full protection. To add it to an environment that has duplicates,
    # resolve them with scripts/dedupe_companies.py, then add a follow-up
    # migration -- this one will already be marked as applied.
    conn = op.get_bind()
    duplicates = conn.execute(sa.text("""
        SELECT user_id, ticker_symbol, count(*) AS n
        FROM company
        GROUP BY user_id, ticker_symbol
        HAVING count(*) > 1
    """)).fetchall()

    if duplicates:
        detail = ', '.join(f'user {d.user_id}/{d.ticker_symbol} x{d.n}'
                           for d in duplicates[:10])
        print(f'SKIPPING {CONSTRAINT_NAME}: {len(duplicates)} duplicate '
              f'(user_id, ticker_symbol) group(s) exist -- {detail}. '
              f'Run scripts/dedupe_companies.py to resolve them, then add a '
              f'follow-up migration to apply the constraint.')
        return

    op.create_unique_constraint(
        CONSTRAINT_NAME, 'company', ['user_id', 'ticker_symbol']
    )


def downgrade():
    # The constraint may have been skipped on this database.
    op.execute(f'ALTER TABLE company DROP CONSTRAINT IF EXISTS {CONSTRAINT_NAME}')
