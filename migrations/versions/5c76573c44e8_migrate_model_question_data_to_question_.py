"""Migrate model_question data to question_bank_item and drop model_question

Revision ID: 5c76573c44e8
Revises: 789c73be7ae4
Create Date: 2026-04-12 12:06:47.184298

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5c76573c44e8'
down_revision = '789c73be7ae4'
branch_labels = None
depends_on = None


def upgrade():
    # Copy model_question rows into question_bank_item, skipping duplicates.
    # Field mapping: question_text -> text, category -> category,
    # source_project_id -> source_project_id, times_used -> times_used,
    # created_at -> created_at, last_used_at -> last_used_at
    op.execute("""
        INSERT INTO question_bank_item
            (user_id, text, category, source_project_id, times_used, last_used_at, created_at)
        SELECT
            mq.user_id,
            mq.question_text,
            mq.category,
            mq.source_project_id,
            mq.times_used,
            mq.last_used_at,
            mq.created_at
        FROM model_question mq
        WHERE NOT EXISTS (
            SELECT 1 FROM question_bank_item qbi
            WHERE qbi.user_id = mq.user_id AND qbi.text = mq.question_text
        )
    """)

    op.drop_table('model_question')


def downgrade():
    # Recreate model_question table (data cannot be fully restored)
    op.create_table('model_question',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False, index=True),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('source_project_id', sa.Integer(),
                   sa.ForeignKey('research_project.id', ondelete='SET NULL'), nullable=True),
        sa.Column('times_used', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
    )
