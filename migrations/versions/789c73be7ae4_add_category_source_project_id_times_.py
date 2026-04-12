"""Add category, source_project_id, times_used, last_used_at to QuestionBankItem

Revision ID: 789c73be7ae4
Revises: 8eefeadbe133
Create Date: 2026-04-11 23:33:06.046212

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '789c73be7ae4'
down_revision = '8eefeadbe133'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('question_bank_item', schema=None) as batch_op:
        batch_op.add_column(sa.Column('category', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('source_project_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('times_used', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('last_used_at', sa.DateTime(), nullable=True))
        batch_op.create_foreign_key(
            'fk_question_bank_item_source_project',
            'research_project', ['source_project_id'], ['id'],
            ondelete='SET NULL'
        )


def downgrade():
    with op.batch_alter_table('question_bank_item', schema=None) as batch_op:
        batch_op.drop_constraint('fk_question_bank_item_source_project', type_='foreignkey')
        batch_op.drop_column('last_used_at')
        batch_op.drop_column('times_used')
        batch_op.drop_column('source_project_id')
        batch_op.drop_column('category')
