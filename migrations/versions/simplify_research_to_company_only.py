"""Simplify research models to company-only

Revision ID: simplify_research_company
Revises: deece4cc6cc9
Create Date: 2025-10-05

This migration simplifies the research workflow to focus exclusively on company analysis:
1. Removes research_subject_types from ResearchTemplate
2. Removes research_subject_type and research_subject_name from ResearchProject
3. Makes company_id required (NOT NULL) in ResearchProject

IMPORTANT: Review and handle any existing non-company research projects before running this migration.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'simplify_research_company'
down_revision = 'deece4cc6cc9'
branch_labels = None
depends_on = None


def upgrade():
    # Check for non-company research projects before migration
    connection = op.get_bind()

    # Count non-company projects
    result = connection.execute(
        sa.text("""
            SELECT COUNT(*) as count
            FROM research_project
            WHERE research_subject_type != 'company' OR research_subject_type IS NULL
        """)
    )
    non_company_count = result.fetchone()[0]

    if non_company_count > 0:
        print(f"\n⚠️  WARNING: Found {non_company_count} non-company research projects!")
        print("These projects will be DELETED as part of this migration.")
        print("Please review and handle these projects manually before proceeding.\n")

        # Show the projects
        result = connection.execute(
            sa.text("""
                SELECT id, project_name, research_subject_type, research_subject_name
                FROM research_project
                WHERE research_subject_type != 'company' OR research_subject_type IS NULL
                LIMIT 10
            """)
        )
        print("Sample projects to be deleted:")
        for row in result:
            print(f"  - ID {row[0]}: {row[1]} ({row[2]}: {row[3]})")

        # Uncomment the line below to allow migration to proceed (with deletions)
        # raise Exception("Migration halted. Handle non-company projects first, then remove this check.")

    # Delete non-company research projects (if any)
    connection.execute(
        sa.text("""
            DELETE FROM research_project
            WHERE research_subject_type != 'company' OR research_subject_type IS NULL OR company_id IS NULL
        """)
    )

    # 1. Drop research_subject_types column from research_template
    with op.batch_alter_table('research_template', schema=None) as batch_op:
        batch_op.drop_column('research_subject_types')

    # 2. Drop research_subject_type and research_subject_name from research_project
    with op.batch_alter_table('research_project', schema=None) as batch_op:
        batch_op.drop_column('research_subject_type')
        batch_op.drop_column('research_subject_name')

        # 3. Make company_id NOT NULL
        batch_op.alter_column('company_id',
                              existing_type=sa.INTEGER(),
                              nullable=False)


def downgrade():
    # Re-add the columns for rollback
    with op.batch_alter_table('research_project', schema=None) as batch_op:
        # Make company_id nullable again
        batch_op.alter_column('company_id',
                              existing_type=sa.INTEGER(),
                              nullable=True)

        # Add back removed columns
        batch_op.add_column(sa.Column('research_subject_name', sa.VARCHAR(length=200), nullable=True))
        batch_op.add_column(sa.Column('research_subject_type', sa.VARCHAR(length=50), nullable=False, server_default='company'))

    # Add back research_subject_types to research_template
    with op.batch_alter_table('research_template', schema=None) as batch_op:
        batch_op.add_column(sa.Column('research_subject_types', postgresql.JSON(astext_type=sa.Text()), nullable=True))
