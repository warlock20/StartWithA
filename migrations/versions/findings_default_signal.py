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

"""findings default signal

A finding's title now holds its signal. Existing findings were titled with
their type label ('Red Flag', 'Green Flag', 'Must Exit') or nothing; they get
the 'Default' signal. Downgrade restores the type labels.

Revision ID: findings_default_signal
Revises: findings_to_journal_entries
Create Date: 2026-10-15

"""
from alembic import op
import sqlalchemy as sa


revision = 'findings_default_signal'
down_revision = 'findings_to_journal_entries'
branch_labels = None
depends_on = None

_LABELS = {
    'red_flag': 'Red Flag',
    'green_flag': 'Green Flag',
    'must_exit': 'Must Exit',
}


def upgrade():
    conn = op.get_bind()
    for entry_type, label in _LABELS.items():
        conn.execute(sa.text(
            "UPDATE journal_entry SET title = 'Default' "
            "WHERE entry_type = :entry_type "
            "AND (title IS NULL OR TRIM(title) = '' OR title = :label)"
        ), {'entry_type': entry_type, 'label': label})


def downgrade():
    conn = op.get_bind()
    for entry_type, label in _LABELS.items():
        conn.execute(sa.text(
            "UPDATE journal_entry SET title = :label "
            "WHERE entry_type = :entry_type AND title = 'Default'"
        ), {'entry_type': entry_type, 'label': label})
