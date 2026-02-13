"""Rename research_session and research_answer tables to checklist_analysis and checklist_answer

Revision ID: rename_checklist_analysis
Revises: add_continuous_learning_tracking
Create Date: 2025-12-15

This migration renames the research session models to better reflect their purpose:
- research_session table → checklist_analysis table
- research_answer table → checklist_answer table
- research_session_id column → checklist_analysis_id column
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'rename_checklist_analysis'
down_revision = 'add_continuous_learning_tracking'
branch_labels = None
depends_on = None


def upgrade():
    # Rename tables
    op.rename_table('research_session', 'checklist_analysis')
    op.rename_table('research_answer', 'checklist_answer')

    # Rename foreign key column in checklist_answer table
    with op.batch_alter_table('checklist_answer', schema=None) as batch_op:
        # Drop the old foreign key constraint first
        batch_op.drop_constraint('research_answer_research_session_id_fkey', type_='foreignkey')

        # Rename the column
        batch_op.alter_column('research_session_id',
                             new_column_name='checklist_analysis_id',
                             existing_type=sa.Integer(),
                             nullable=False)

        # Add the new foreign key constraint
        batch_op.create_foreign_key(
            'checklist_answer_checklist_analysis_id_fkey',
            'checklist_analysis',
            ['checklist_analysis_id'],
            ['id']
        )


def downgrade():
    # Reverse the changes

    # Rename column back in checklist_answer table
    with op.batch_alter_table('checklist_answer', schema=None) as batch_op:
        # Drop the new foreign key constraint
        batch_op.drop_constraint('checklist_answer_checklist_analysis_id_fkey', type_='foreignkey')

        # Rename the column back
        batch_op.alter_column('checklist_analysis_id',
                             new_column_name='research_session_id',
                             existing_type=sa.Integer(),
                             nullable=False)

        # Add the old foreign key constraint back
        batch_op.create_foreign_key(
            'research_answer_research_session_id_fkey',
            'research_session',
            ['research_session_id'],
            ['id']
        )

    # Rename tables back
    op.rename_table('checklist_answer', 'research_answer')
    op.rename_table('checklist_analysis', 'research_session')
