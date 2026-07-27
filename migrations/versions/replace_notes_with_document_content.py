"""Replace notes with document_content in sector_analysis

Revision ID: replace_notes_document
Revises: add_key_takeaways_sector
Create Date: 2025-10-09

This migration:
1. Adds document_content column to sector_analysis
2. Migrates existing notes data to document_content
3. Drops the legacy notes column

The document_content field is used for the Document View editor,
while atomic notes are stored in the sector_sections/sector_notes tables.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'replace_notes_document'
down_revision = 'add_key_takeaways_sector'
branch_labels = None
depends_on = None


def upgrade():
    # Add document_content column
    with op.batch_alter_table('sector_analysis', schema=None) as batch_op:
        batch_op.add_column(sa.Column('document_content', sa.Text(), nullable=True))

    # Migrate existing notes data to document_content
    connection = op.get_bind()
    connection.execute(
        sa.text("""
            UPDATE sector_analysis
            SET document_content = notes
            WHERE notes IS NOT NULL AND notes != ''
        """)
    )

    # Drop the legacy notes column
    with op.batch_alter_table('sector_analysis', schema=None) as batch_op:
        batch_op.drop_column('notes')


def downgrade():
    # Add back the notes column
    with op.batch_alter_table('sector_analysis', schema=None) as batch_op:
        batch_op.add_column(sa.Column('notes', sa.Text(), nullable=True))

    # Migrate document_content back to notes
    connection = op.get_bind()
    connection.execute(
        sa.text("""
            UPDATE sector_analysis
            SET notes = document_content
            WHERE document_content IS NOT NULL AND document_content != ''
        """)
    )

    # Drop document_content column
    with op.batch_alter_table('sector_analysis', schema=None) as batch_op:
        batch_op.drop_column('document_content')
