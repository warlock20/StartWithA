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

"""Add companion agenda system configs (issue #317)

Revision ID: add_agenda_config
Revises: company_sweep_link
Create Date: 2026-09-25

Thresholds for the companion's get_agenda tool, editable from the admin panel
(System Config, category 'companion'). Defaults mirror the fallbacks in
app/services/argos/agenda.py.
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'add_agenda_config'
down_revision = 'company_sweep_link'
branch_labels = None
depends_on = None

_KEYS = (
    'agenda_default_horizon_days', 'agenda_max_horizon_days',
    'agenda_stalled_after_days', 'agenda_max_items',
)


def upgrade():
    op.execute("""
        INSERT INTO system_config (key, value, description, category, data_type, min_value, max_value, created_at, updated_at)
        VALUES
        ('agenda_default_horizon_days', '30', 'Companion agenda: days ahead to look for due checkpoints when no horizon is asked for', 'companion', 'number', 1, 365, NOW(), NOW()),
        ('agenda_max_horizon_days', '365', 'Companion agenda: largest horizon (days) the companion may request', 'companion', 'number', 1, 3650, NOW(), NOW()),
        ('agenda_stalled_after_days', '45', 'Companion agenda: an active research project untouched for this many days counts as stalled', 'companion', 'number', 1, 365, NOW(), NOW()),
        ('agenda_max_items', '15', 'Companion agenda: maximum items listed per section (totals are always reported)', 'companion', 'number', 1, 100, NOW(), NOW())
        ON CONFLICT (key) DO NOTHING
    """)


def downgrade():
    keys = ", ".join(f"'{k}'" for k in _KEYS)
    op.execute(f"DELETE FROM system_config WHERE key IN ({keys})")
