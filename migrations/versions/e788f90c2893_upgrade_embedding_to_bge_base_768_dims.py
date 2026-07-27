"""upgrade_embedding_to_bge_base_768_dims

Revision ID: e788f90c2893
Revises: 93558ae4f875
Create Date: 2026-02-23 06:21:18.011361

Upgrades embedding model from all-MiniLM-L6-v2 (384 dims) to BAAI/bge-base-en-v1.5 (768 dims).
This migration drops and recreates the embedding_vector column, clearing all existing embeddings.
Embeddings will be regenerated on-demand by Argos as needed.
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision = 'e788f90c2893'
down_revision = '93558ae4f875'
branch_labels = None
depends_on = None


def upgrade():
    # pgvector doesn't support ALTER COLUMN TYPE for dimension changes
    # We must drop and recreate the column (this clears all embeddings)
    op.drop_column('embedding_store', 'embedding_vector')
    op.add_column('embedding_store', sa.Column('embedding_vector', Vector(768), nullable=True))


def downgrade():
    # Downgrade back to 384 dimensions (also clears embeddings)
    op.drop_column('embedding_store', 'embedding_vector')
    op.add_column('embedding_store', sa.Column('embedding_vector', Vector(384), nullable=True))
