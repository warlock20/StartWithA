"""Add Circle of Competence and Too Hard tracking fields

Revision ID: add_coc_too_hard
Revises: add_unified_sector
Create Date: 2025-10-18

This migration:
1. Adds Circle of Competence tracking to ResearchProject and IdeaPipeline
2. Adds Too Hard workflow fields to ResearchProject
3. Handles existing paused projects (converts to active)

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.orm import Session


# revision identifiers, used by Alembic.
revision = 'add_coc_too_hard'
down_revision = 'add_unified_sector'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add new columns to research_project table
    op.add_column('research_project', sa.Column('within_circle_of_competence', sa.String(length=20), nullable=True))
    op.add_column('research_project', sa.Column('too_hard_reason', sa.String(length=100), nullable=True))
    op.add_column('research_project', sa.Column('too_hard_notes', sa.Text(), nullable=True))
    op.add_column('research_project', sa.Column('abandoned_at', sa.DateTime(), nullable=True))

    # 2. Add new column to idea_pipeline table
    op.add_column('idea_pipeline', sa.Column('within_circle_of_competence', sa.String(length=20), nullable=True))

    # 3. Handle existing paused projects - convert to active
    # This is a business logic decision: paused projects are just temporarily stopped active projects
    bind = op.get_bind()
    session = Session(bind=bind)

    # Count paused projects before migration
    paused_count = session.execute(
        text("SELECT COUNT(*) FROM research_project WHERE status = 'paused'")
    ).scalar()

    if paused_count > 0:
        print(f"Converting {paused_count} paused projects to active status...")

        # Convert paused to active
        session.execute(
            text("UPDATE research_project SET status = 'active' WHERE status = 'paused'")
        )

        session.commit()
        print(f"Successfully converted {paused_count} projects to active status.")


def downgrade():
    # Remove new columns
    op.drop_column('idea_pipeline', 'within_circle_of_competence')
    op.drop_column('research_project', 'abandoned_at')
    op.drop_column('research_project', 'too_hard_notes')
    op.drop_column('research_project', 'too_hard_reason')
    op.drop_column('research_project', 'within_circle_of_competence')

    # Note: We cannot restore the original 'paused' status as we don't know
    # which projects were originally paused. They will remain as 'active'.
