"""Add cascade delete relationships for foreign key constraints

Revision ID: b9dec42c43a0
Revises: cbc9190021f4
Create Date: 2025-09-24 15:55:13.445938

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b9dec42c43a0'
down_revision = 'cbc9190021f4'
branch_labels = None
depends_on = None


def upgrade():
    # Add CASCADE delete to research_log.idea_id foreign key constraint
    # This will automatically delete research_log entries when idea_pipeline is deleted
    op.drop_constraint('research_log_idea_id_fkey', 'research_log', type_='foreignkey')
    op.create_foreign_key(
        'research_log_idea_id_fkey',
        'research_log',
        'idea_pipeline',
        ['idea_id'],
        ['id'],
        ondelete='CASCADE'
    )

    # Also add CASCADE delete to research_log.project_id foreign key constraint
    # This will automatically delete research_log entries when research_project is deleted
    op.drop_constraint('research_log_project_id_fkey', 'research_log', type_='foreignkey')
    op.create_foreign_key(
        'research_log_project_id_fkey',
        'research_log',
        'research_project',
        ['project_id'],
        ['id'],
        ondelete='CASCADE'
    )


def downgrade():
    # Revert CASCADE delete constraints back to original
    op.drop_constraint('research_log_idea_id_fkey', 'research_log', type_='foreignkey')
    op.create_foreign_key(
        'research_log_idea_id_fkey',
        'research_log',
        'idea_pipeline',
        ['idea_id'],
        ['id']
    )

    op.drop_constraint('research_log_project_id_fkey', 'research_log', type_='foreignkey')
    op.create_foreign_key(
        'research_log_project_id_fkey',
        'research_log',
        'research_project',
        ['project_id'],
        ['id']
    )
