"""Add company_id to free_research_question, make project_id and step_index nullable

Revision ID: standalone_free_research
Revises: af4cbdebff75
Create Date: 2026-05-17
"""
from alembic import op
import sqlalchemy as sa

revision = 'standalone_free_research'
down_revision = 'af4cbdebff75'
branch_labels = None
depends_on = None


def upgrade():
    # Step 1: Add company_id as nullable (must be nullable for backfill)
    with op.batch_alter_table('free_research_question', schema=None) as batch_op:
        batch_op.add_column(sa.Column('company_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_free_research_question_company_id',
            'company', ['company_id'], ['id']
        )
        batch_op.create_index('ix_free_research_question_company_id', ['company_id'])

    # Step 2: Backfill company_id from research_project for existing rows
    op.execute(
        "UPDATE free_research_question "
        "SET company_id = ("
        "    SELECT research_project.company_id "
        "    FROM research_project "
        "    WHERE research_project.id = free_research_question.project_id"
        ") "
        "WHERE project_id IS NOT NULL"
    )

    # Step 3: Make project_id and step_index nullable
    with op.batch_alter_table('free_research_question', schema=None) as batch_op:
        batch_op.alter_column('project_id', existing_type=sa.Integer(), nullable=True)
        batch_op.alter_column('step_index', existing_type=sa.Integer(), nullable=True)


def downgrade():
    # Delete any standalone questions (project_id IS NULL) before making column NOT NULL
    op.execute(
        "DELETE FROM free_research_question WHERE project_id IS NULL"
    )

    with op.batch_alter_table('free_research_question', schema=None) as batch_op:
        batch_op.alter_column('step_index', existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column('project_id', existing_type=sa.Integer(), nullable=False)
        batch_op.drop_index('ix_free_research_question_company_id')
        batch_op.drop_constraint('fk_free_research_question_company_id', type_='foreignkey')
        batch_op.drop_column('company_id')
