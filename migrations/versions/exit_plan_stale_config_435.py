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

"""Add exit_plan_stale_days system config (issue #435)

Revision ID: exit_plan_stale_config_435
Revises: expected_cagr_rename
Create Date: 2026-11-21

Threshold for the position coverage warnings, editable from the admin panel
(System Config, category 'portfolio_alerts'). Default mirrors
DEFAULT_EXIT_PLAN_STALE_DAYS in app/services/position_coverage.py.
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'exit_plan_stale_config_435'
down_revision = 'expected_cagr_rename'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        INSERT INTO system_config (key, value, description, category, data_type, min_value, max_value, created_at, updated_at)
        VALUES
        ('exit_plan_stale_days', '90', 'Coverage: an exit plan with no rule reviewed or updated in this many days is stale', 'portfolio_alerts', 'number', 1, 3650, NOW(), NOW())
        ON CONFLICT (key) DO NOTHING
    """)


def downgrade():
    op.execute("DELETE FROM system_config WHERE key = 'exit_plan_stale_days'")
