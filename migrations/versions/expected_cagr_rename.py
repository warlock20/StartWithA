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

"""the expected return is a CAGR: rename expected_return to expected_cagr

Renames decision_journal.expected_return, research_outcome.expected_return_pct
and the 'expected_return' key in thesis_evolution.key_metrics. Values are kept
as they are. Entries that may have been a total return (a timeframe other than
12 months, where a total and a CAGR differ) are copied into expected_cagr_review,
which `flask expected-cagr review` lists.

Revision ID: expected_cagr_rename
Revises: exit_plan_434
Create Date: 2026-11-21
"""
from alembic import op
import sqlalchemy as sa


revision = 'expected_cagr_rename'
down_revision = 'exit_plan_434'
branch_labels = None
depends_on = None


def _rename_key_metric(old, new):
    op.execute(f"""
        UPDATE thesis_evolution
        SET key_metrics = ((key_metrics::jsonb - '{old}')
                           || jsonb_build_object('{new}', key_metrics::jsonb -> '{old}'))::json
        WHERE key_metrics IS NOT NULL
          AND json_typeof(key_metrics) = 'object'
          AND jsonb_exists(key_metrics::jsonb, '{old}')
    """)


def upgrade():
    op.alter_column('decision_journal', 'expected_return', new_column_name='expected_cagr')
    op.alter_column('research_outcome', 'expected_return_pct', new_column_name='expected_cagr_pct')
    _rename_key_metric('expected_return', 'expected_cagr')

    op.create_table(
        'expected_cagr_review',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('kind', sa.String(10), nullable=False),
        sa.Column('entry_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False, index=True),
        sa.Column('original_value', sa.Float(), nullable=False),
        sa.Column('timeframe_months', sa.Integer(), nullable=False),
        sa.Column('resolution', sa.String(10), nullable=True),
        sa.Column('resolved_value', sa.Float(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('kind', 'entry_id', name='uq_expected_cagr_review_entry'),
    )
    # A total and a CAGR read the same over 12 months (and a missing timeframe
    # was taken as 12), so only other timeframes are queued for review
    op.execute("""
        INSERT INTO expected_cagr_review (kind, entry_id, user_id, original_value, timeframe_months)
        SELECT 'buy', id, user_id, expected_cagr, expected_timeframe
        FROM decision_journal
        WHERE decision_type = 'BUY'
          AND expected_cagr IS NOT NULL
          AND expected_timeframe IS NOT NULL AND expected_timeframe <> 12
          AND is_imported IS NOT TRUE
    """)
    op.execute("""
        INSERT INTO expected_cagr_review (kind, entry_id, user_id, original_value, timeframe_months)
        SELECT 'thesis', id, user_id,
               (key_metrics::jsonb ->> 'expected_cagr')::float,
               (key_metrics::jsonb ->> 'expected_timeframe')::numeric::int
        FROM thesis_evolution
        WHERE key_metrics IS NOT NULL
          AND json_typeof(key_metrics) = 'object'
          AND jsonb_typeof(key_metrics::jsonb -> 'expected_cagr') = 'number'
          AND jsonb_typeof(key_metrics::jsonb -> 'expected_timeframe') = 'number'
          AND (key_metrics::jsonb ->> 'expected_timeframe')::numeric <> 12
    """)


def downgrade():
    op.drop_table('expected_cagr_review')
    _rename_key_metric('expected_cagr', 'expected_return')
    op.alter_column('research_outcome', 'expected_cagr_pct', new_column_name='expected_return_pct')
    op.alter_column('decision_journal', 'expected_cagr', new_column_name='expected_return')
