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

"""knowledge index: pieces, context and change detection (#389)

Each knowledge item is now split into pieces, so a chunk is keyed by
(source_type, source_id, chunk_index). Each piece stores its context and how it
was made (`llm` or `prefix`), the hash of its whole item, and the embedding
model, so the nightly job can skip unchanged items and redo stale ones.

On the user: the opt-out from AI-written context, and the start time of the
last indexing run that finished (the watermark for changed items).

Revision ID: knowledge_index_389
Revises: scheduled_job_run
Create Date: 2026-10-30

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'knowledge_index_389'
down_revision = 'scheduled_job_run'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('knowledge_chunk', schema=None) as batch_op:
        batch_op.add_column(sa.Column('chunk_index', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('context', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('context_method', sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('content_hash', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('embedding_model', sa.String(length=120), nullable=True))
        batch_op.drop_constraint('uq_knowledge_source', type_='unique')
        batch_op.create_unique_constraint(
            'uq_knowledge_source_piece', ['source_type', 'source_id', 'chunk_index'])

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'knowledge_context_enabled', sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column('knowledge_indexed_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('knowledge_indexed_at')
        batch_op.drop_column('knowledge_context_enabled')

    # The old key allows one row per item, so pieces after the first must go.
    op.execute('DELETE FROM knowledge_chunk WHERE chunk_index > 0')
    with op.batch_alter_table('knowledge_chunk', schema=None) as batch_op:
        batch_op.drop_constraint('uq_knowledge_source_piece', type_='unique')
        batch_op.create_unique_constraint('uq_knowledge_source', ['source_type', 'source_id'])
        batch_op.drop_column('embedding_model')
        batch_op.drop_column('content_hash')
        batch_op.drop_column('context_method')
        batch_op.drop_column('context')
        batch_op.drop_column('chunk_index')
