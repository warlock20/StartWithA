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

"""reconcile schema drift

The dev/prod databases had drifted from the models with no migration recording
the difference (issue #306). Two schema differences remained un-migrated:

1. ``uq_company_user_ticker`` on ``company (user_id, ticker_symbol)`` -- declared
   in the model but missing from dev/prod, because the ``unique_company_ticker``
   migration self-skips when duplicate companies exist and duplicates existed at
   the time it ran. They have since been resolved, so the constraint can finally
   be applied where it is still missing.

2. ``free_research_question.company_id`` -- the model declares it NOT NULL, but
   the column was added nullable (``standalone_free_research``, for a backfill)
   and never tightened.

The eight compound performance indexes from ``e059bebc4087`` were the third part
of the drift: they existed in every database but were never declared in the
models, so autogenerate kept wanting to DROP them. Those are fixed purely in the
models (their ``__table_args__``) -- no schema change is needed here, since the
indexes already exist -- and that is why this migration does not touch them.

This migration is written to be safe on BOTH:
- fresh databases, where ``unique_company_ticker`` already created the constraint
  (no duplicates on an empty DB) -- the add is skipped as a no-op; and
- drifted dev/prod, where the constraint is absent -- it is added.

Revision ID: reconcile_schema_drift
Revises: unique_company_ticker
Create Date: 2026-07-25

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'reconcile_schema_drift'
down_revision = 'unique_company_ticker'
branch_labels = None
depends_on = None

CONSTRAINT_NAME = 'uq_company_user_ticker'


def upgrade():
    conn = op.get_bind()

    # --- uq_company_user_ticker ------------------------------------------
    # Only add it where it is still missing (it is already present on fresh
    # databases). If duplicates somehow still exist, skip rather than fail --
    # a blocked deploy helps nobody, and dedupe is a deliberate, non-automatic
    # step (see scripts/dedupe_companies.py).
    already_present = conn.execute(sa.text(
        "SELECT 1 FROM pg_constraint WHERE conname = :name"
    ), {"name": CONSTRAINT_NAME}).scalar()

    if not already_present:
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
        else:
            op.create_unique_constraint(
                CONSTRAINT_NAME, 'company', ['user_id', 'ticker_symbol']
            )

    # --- free_research_question.company_id NOT NULL ----------------------
    # Every research question references a company; the model has always declared
    # this NOT NULL. Fails loudly if any NULL rows exist -- verify (and backfill)
    # before deploying to an environment that might have them.
    op.alter_column(
        'free_research_question', 'company_id',
        existing_type=sa.Integer(), nullable=False,
    )


def downgrade():
    op.alter_column(
        'free_research_question', 'company_id',
        existing_type=sa.Integer(), nullable=True,
    )
    # DROP IF EXISTS: the constraint may have been a no-op add on this database.
    op.execute(f'ALTER TABLE company DROP CONSTRAINT IF EXISTS {CONSTRAINT_NAME}')
