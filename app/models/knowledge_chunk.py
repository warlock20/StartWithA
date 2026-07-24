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
KnowledgeChunk — one embedded summary of a piece of the user's knowledge.

The companion's `search_my_knowledge` tool retrieves across four sources
(research findings, journal entries, decision journals, saved resources).
Each source item is summarised, embedded once (BGE-base, 768 dims, pgvector),
and stored here keyed by (source_type, source_id) so re-indexing is idempotent.

Matches the existing embedding infra: `EmbeddingStore` uses the same
`Vector(768)` pgvector column type.
"""

from pgvector.sqlalchemy import Vector

from app import db
from app.utils.time_utils import now_utc


class KnowledgeChunk(db.Model):
    """An embedded, summarised chunk of one user's knowledge."""

    __tablename__ = 'knowledge_chunk'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'),
        nullable=False, index=True)
    company_id = db.Column(
        db.Integer, db.ForeignKey('company.id', ondelete='CASCADE'),
        nullable=True, index=True)

    # 'finding' | 'journal' | 'decision' | 'resource'
    source_type = db.Column(db.String(20), nullable=False, index=True)
    source_id = db.Column(db.Integer, nullable=False)

    title = db.Column(db.String(300))
    summary = db.Column(db.Text, nullable=False)  # the embedded string

    # BGE-base-en-v1.5, 768 dims (same as EmbeddingStore). Requires pgvector.
    embedding = db.Column(Vector(768), nullable=True)

    token_estimate = db.Column(db.Integer, default=0)
    updated_at = db.Column(db.DateTime, default=now_utc, onupdate=now_utc)

    __table_args__ = (
        db.UniqueConstraint('source_type', 'source_id', name='uq_knowledge_source'),
    )

    def __repr__(self):
        return f'<KnowledgeChunk {self.source_type} #{self.source_id}>'
