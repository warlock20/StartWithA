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

"""findings to journal entries

Red flags, green flags and must-exit criteria move from JSON lists on
research_project to journal entries on the company (entry_type 'red_flag',
'green_flag', 'must_exit'), so they can be recorded without a research
project. Each list item becomes one entry linked to the company and the
project; the three columns are then dropped.

Downgrade moves entries back onto the company's research project. Findings
on companies without a research project stay as journal entries.

Revision ID: findings_to_journal_entries
Revises: 27e83f19dd00
Create Date: 2026-10-14

"""
import json
from datetime import datetime, timedelta, timezone

from alembic import op
import sqlalchemy as sa


revision = 'findings_to_journal_entries'
down_revision = '27e83f19dd00'
branch_labels = None
depends_on = None


# (column on research_project, journal entry_type, entry title, sentiment)
FINDINGS = [
    ('red_flags', 'red_flag', 'Red Flag', 'bearish'),
    ('green_flags', 'green_flag', 'Green Flag', 'bullish'),
    ('must_exit_criteria', 'must_exit', 'Must Exit', None),
]

journal_entry = sa.table(
    'journal_entry',
    sa.column('id', sa.Integer),
    sa.column('user_id', sa.Integer),
    sa.column('company_id', sa.Integer),
    sa.column('project_id', sa.Integer),
    sa.column('entry_type', sa.String),
    sa.column('title', sa.String),
    sa.column('content', sa.Text),
    sa.column('sentiment', sa.String),
    sa.column('source', sa.String),
    sa.column('tags', sa.JSON),
    sa.column('is_starred', sa.Boolean),
    sa.column('is_archived', sa.Boolean),
    sa.column('review_count', sa.Integer),
    sa.column('created_at', sa.DateTime),
    sa.column('updated_at', sa.DateTime),
)


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return [value] if value.strip() else []
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if v is not None and str(v).strip()]


def upgrade():
    conn = op.get_bind()
    projects = conn.execute(sa.text(
        'SELECT id, user_id, company_id, red_flags, green_flags, must_exit_criteria, '
        'decision_date, last_worked_at, created_at FROM research_project'
    )).mappings().all()

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    rows = []
    for p in projects:
        base = p['decision_date'] or p['last_worked_at'] or p['created_at'] or now
        if isinstance(base, str):
            base = datetime.fromisoformat(base)
        offset = 0
        for column, entry_type, title, sentiment in FINDINGS:
            for text in _as_list(p[column]):
                # Step by a microsecond so list order survives created_at ordering.
                stamp = base + timedelta(microseconds=offset)
                offset += 1
                rows.append({
                    'user_id': p['user_id'],
                    'company_id': p['company_id'],
                    'project_id': p['id'],
                    'entry_type': entry_type,
                    'title': title,
                    'content': text,
                    'sentiment': sentiment,
                    'source': 'finding',
                    'tags': [],
                    'is_starred': False,
                    'is_archived': False,
                    'review_count': 0,
                    'created_at': stamp,
                    'updated_at': stamp,
                })
    if rows:
        op.bulk_insert(journal_entry, rows)

    with op.batch_alter_table('research_project', schema=None) as batch_op:
        batch_op.drop_column('red_flags')
        batch_op.drop_column('green_flags')
        batch_op.drop_column('must_exit_criteria')


def downgrade():
    with op.batch_alter_table('research_project', schema=None) as batch_op:
        batch_op.add_column(sa.Column('red_flags', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('green_flags', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('must_exit_criteria', sa.JSON(), nullable=True))

    conn = op.get_bind()
    projects = conn.execute(sa.text(
        'SELECT id, user_id, company_id FROM research_project'
    )).mappings().all()

    research_project = sa.table(
        'research_project',
        sa.column('id', sa.Integer),
        sa.column('red_flags', sa.JSON),
        sa.column('green_flags', sa.JSON),
        sa.column('must_exit_criteria', sa.JSON),
    )

    for p in projects:
        values = {}
        moved_ids = []
        for column, entry_type, _title, _sentiment in FINDINGS:
            entries = conn.execute(sa.text(
                'SELECT id, content FROM journal_entry '
                'WHERE user_id = :uid AND company_id = :cid AND entry_type = :etype '
                'ORDER BY created_at, id'
            ), {'uid': p['user_id'], 'cid': p['company_id'], 'etype': entry_type}).mappings().all()
            values[column] = [e['content'] for e in entries]
            moved_ids.extend(e['id'] for e in entries)
        conn.execute(
            research_project.update().where(research_project.c.id == p['id']).values(**values)
        )
        if moved_ids:
            conn.execute(journal_entry.delete().where(journal_entry.c.id.in_(moved_ids)))
