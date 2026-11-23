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

"""Flag outcomes of trades opened by a merger or spin-off (issue #451)

Revision ID: research_outcome_is_received_451
Revises: selection_assist_setting
Create Date: 2026-11-23

research_outcome.is_received is true when a corporate action handed over the
shares, so the trade has no research decision behind it.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'research_outcome_is_received_451'
down_revision = 'selection_assist_setting'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('research_outcome',
                  sa.Column('is_received', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column('research_outcome', 'is_received')
