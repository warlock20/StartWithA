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
    # Duplicates must be resolved before this can apply. Fail with a message
    # that says what to do rather than a bare IntegrityError.
    conn = op.get_bind()
    duplicates = conn.execute(sa.text("""
        SELECT user_id, ticker_symbol, count(*) AS n
        FROM company
        GROUP BY user_id, ticker_symbol
        HAVING count(*) > 1
    """)).fetchall()

    if duplicates:
        detail = ', '.join(f'user {d.user_id}/{d.ticker_symbol} x{d.n}' for d in duplicates[:10])
        raise RuntimeError(
            f'Cannot add {CONSTRAINT_NAME}: {len(duplicates)} duplicate '
            f'(user_id, ticker_symbol) group(s) still exist -- {detail}. '
            'Merge or remove the duplicates before running this migration.'
        )

    op.create_unique_constraint(
        CONSTRAINT_NAME, 'company', ['user_id', 'ticker_symbol']
    )


def downgrade():
    op.drop_constraint(CONSTRAINT_NAME, 'company', type_='unique')
