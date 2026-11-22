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

"""Background-AI web search allowance (issue #437)

Revision ID: exit_watch_search_437
Revises: user_monitor_setting_436
Create Date: 2026-11-22

prompt_usage_log.web_searches counts the searches a logged call made;
research_settings.background_search_allowance is the user's monthly allowance
(NULL = default 150); system_config background_search_allowance_max is the
admin ceiling for it.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'exit_watch_search_437'
down_revision = 'user_monitor_setting_436'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('prompt_usage_log', sa.Column('web_searches', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('research_settings', sa.Column('background_search_allowance', sa.Integer(), nullable=True))
    op.execute("""
        INSERT INTO system_config (key, value, description, category, data_type, min_value, max_value, created_at, updated_at)
        VALUES
        ('background_search_allowance_max', '500', 'Background AI: the most web searches a month a user may allow', 'background_ai', 'number', 0, 10000, NOW(), NOW())
        ON CONFLICT (key) DO NOTHING
    """)


def downgrade():
    op.execute("DELETE FROM system_config WHERE key = 'background_search_allowance_max'")
    op.drop_column('research_settings', 'background_search_allowance')
    op.drop_column('prompt_usage_log', 'web_searches')
