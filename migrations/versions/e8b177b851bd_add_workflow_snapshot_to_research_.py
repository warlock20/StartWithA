"""add workflow_snapshot to research_project

Revision ID: e8b177b851bd
Revises: 40a56ad48179
Create Date: 2026-05-22 18:52:12.062389

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e8b177b851bd'
down_revision = '40a56ad48179'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('research_project', schema=None) as batch_op:
        batch_op.add_column(sa.Column('workflow_snapshot', sa.JSON(), nullable=True))

    # Backfill existing projects with their template's workflow_steps
    connection = op.get_bind()
    connection.execute(sa.text("""
        UPDATE research_project
        SET workflow_snapshot = (
            SELECT workflow_steps
            FROM research_template
            WHERE research_template.id = research_project.template_id
        )
        WHERE workflow_snapshot IS NULL
          AND template_id IS NOT NULL
    """))


def downgrade():
    with op.batch_alter_table('research_project', schema=None) as batch_op:
        batch_op.drop_column('workflow_snapshot')
