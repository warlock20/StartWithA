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

"""
KnowledgeChunk — one embedded piece of an item of the user's knowledge.

The companion's `search_my_knowledge` tool retrieves across four sources
(journal entries, including findings; decision journals; saved resources;
logged mistakes). The indexer (`services/argos/knowledge_index.py`) splits each
item into pieces of about 200 words, gives each piece a short context (written
by an LLM, or a free "<company> — <title>:" prefix), and embeds context + piece.
One row per piece, keyed by (source_type, source_id, chunk_index).

The default embedding provider is `gemini-embedding-001` truncated to 768
dims, the same `Vector(768)` pgvector column type `EmbeddingStore` uses.
`embedding_model` records which model made each vector, because vectors from
different models can't be compared.
"""

from pgvector.sqlalchemy import Vector

from app import db
from app.utils.time_utils import now_utc


class KnowledgeChunk(db.Model):
    """One embedded piece of one user's knowledge."""

    __tablename__ = 'knowledge_chunk'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'),
        nullable=False, index=True)
    company_id = db.Column(
        db.Integer, db.ForeignKey('company.id', ondelete='CASCADE'),
        nullable=True, index=True)

    # 'journal' | 'decision' | 'resource' | 'mistake'
    source_type = db.Column(db.String(20), nullable=False, index=True)
    source_id = db.Column(db.Integer, nullable=False)
    chunk_index = db.Column(db.Integer, nullable=False, default=0, server_default='0')

    title = db.Column(db.String(300))
    summary = db.Column(db.Text, nullable=False)  # the piece's text
    context = db.Column(db.Text, nullable=True)  # places the piece in its item
    context_method = db.Column(db.String(10), nullable=True)  # 'llm' | 'prefix'
    content_hash = db.Column(db.String(64), nullable=True)  # sha256 of the whole item

    # 768 dims (same as EmbeddingStore). Requires pgvector. NULL when embedding failed.
    embedding = db.Column(Vector(768), nullable=True)
    embedding_model = db.Column(db.String(120), nullable=True)  # e.g. 'gemini/models/gemini-embedding-001'

    token_estimate = db.Column(db.Integer, default=0)
    updated_at = db.Column(db.DateTime, default=now_utc, onupdate=now_utc)

    __table_args__ = (
        db.UniqueConstraint('source_type', 'source_id', 'chunk_index', name='uq_knowledge_source_piece'),
    )

    def __repr__(self):
        return f'<KnowledgeChunk {self.source_type} #{self.source_id}.{self.chunk_index}>'
