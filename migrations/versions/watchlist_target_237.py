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

"""watchlist valuation targets: research_project columns and near-target config

Revision ID: watchlist_target_237
Revises: corporate_actions_399
Create Date: 2026-11-19
"""
from alembic import op
import sqlalchemy as sa


revision = 'watchlist_target_237'
down_revision = 'corporate_actions_399'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('research_project', schema=None) as batch_op:
        batch_op.add_column(sa.Column('watch_target_metric', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('watch_target_value', sa.Numeric(precision=24, scale=4), nullable=True))
        batch_op.add_column(sa.Column('watch_target_currency', sa.String(length=3), nullable=True))
        batch_op.add_column(sa.Column('watch_last_value', sa.Numeric(precision=24, scale=4), nullable=True))
        batch_op.add_column(sa.Column('watch_last_checked_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('watch_target_hit_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('watch_target_dismissed_at', sa.DateTime(), nullable=True))

    op.execute("""
        INSERT INTO system_config (key, value, description, category, data_type, min_value, max_value, created_at, updated_at) VALUES
        ('watchlist_near_target_pct', '0', 'Warn when a watchlist target is within this % (0 = off)', 'watchlist_alerts', 'percent', 0, 25, NOW(), NOW())
        ON CONFLICT (key) DO NOTHING
    """)


def downgrade():
    op.execute("DELETE FROM system_config WHERE key = 'watchlist_near_target_pct'")
    with op.batch_alter_table('research_project', schema=None) as batch_op:
        batch_op.drop_column('watch_target_dismissed_at')
        batch_op.drop_column('watch_target_hit_at')
        batch_op.drop_column('watch_last_checked_at')
        batch_op.drop_column('watch_last_value')
        batch_op.drop_column('watch_target_currency')
        batch_op.drop_column('watch_target_value')
        batch_op.drop_column('watch_target_metric')
