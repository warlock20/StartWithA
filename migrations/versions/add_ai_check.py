# StartWithA
# Copyright (C) 2024-2026 Kiran Mathews
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""add ai check

AI context on checklist questions, and the AI check run / source / evidence tables.
Existing llm_prompt text is copied into ai_context.method.

Revision ID: add_ai_check
Revises: research_reopenings
Create Date: 2026-09-27

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_ai_check'
down_revision = 'research_reopenings'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('checklist_item', sa.Column('ai_context', sa.JSON(), nullable=True))
    op.add_column('question_bank_item', sa.Column('ai_context', sa.JSON(), nullable=True))
    for table in ('checklist_item', 'question_bank_item'):
        op.execute(
            f"UPDATE {table} SET ai_context = json_build_object('method', llm_prompt) "
            f"WHERE llm_prompt IS NOT NULL AND btrim(llm_prompt) <> ''"
        )

    op.create_table(
        'ai_check_run',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('checklist_item_id', sa.Integer(), nullable=False),
        sa.Column('analysis_id', sa.Integer(), nullable=True),
        sa.Column('mode', sa.String(length=20), nullable=False),
        sa.Column('document_ids', sa.JSON(), nullable=False),
        sa.Column('context_snapshot', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('failed_stage', sa.String(length=20), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('models', sa.JSON(), nullable=False),
        sa.Column('tokens_in', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tokens_out', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cache_read_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('web_searches', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('web_fetches', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cost_estimate', sa.Float(), nullable=False, server_default='0'),
        sa.Column('loop_back_used', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.ForeignKeyConstraint(['company_id'], ['company.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['checklist_item_id'], ['checklist_item.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['analysis_id'], ['checklist_analysis.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ai_check_run_user_id', 'ai_check_run', ['user_id'])
    op.create_index('ix_ai_check_run_company_id', 'ai_check_run', ['company_id'])
    op.create_index('ix_ai_check_run_checklist_item_id', 'ai_check_run', ['checklist_item_id'])
    op.create_index('ix_ai_check_run_status', 'ai_check_run', ['status'])
    op.create_index('ix_ai_check_run_user_company_item', 'ai_check_run',
                    ['user_id', 'company_id', 'checklist_item_id'])

    op.create_table(
        'ai_check_source',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('company_resource_id', sa.Integer(), nullable=True),
        sa.Column('url', sa.String(length=1000), nullable=True),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('doc_type', sa.String(length=100), nullable=True),
        sa.Column('period', sa.String(length=50), nullable=True),
        sa.Column('gap_filled', sa.Text(), nullable=True),
        sa.Column('extract_status', sa.String(length=20), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['ai_check_run.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['company_resource_id'], ['company_resource.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ai_check_source_run_id', 'ai_check_source', ['run_id'])

    op.create_table(
        'ai_check_evidence',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('label', sa.String(length=10), nullable=True),
        sa.Column('metric', sa.String(length=300), nullable=False),
        sa.Column('value', sa.String(length=100), nullable=False),
        sa.Column('value_numeric', sa.Float(), nullable=True),
        sa.Column('unit', sa.String(length=50), nullable=True),
        sa.Column('period', sa.String(length=50), nullable=True),
        sa.Column('location', sa.String(length=300), nullable=True),
        sa.Column('quote', sa.Text(), nullable=True),
        sa.Column('verified', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(['run_id'], ['ai_check_run.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_id'], ['ai_check_source.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ai_check_evidence_run_id', 'ai_check_evidence', ['run_id'])
    op.create_index('ix_ai_check_evidence_source_id', 'ai_check_evidence', ['source_id'])


def downgrade():
    op.drop_index('ix_ai_check_evidence_source_id', table_name='ai_check_evidence')
    op.drop_index('ix_ai_check_evidence_run_id', table_name='ai_check_evidence')
    op.drop_table('ai_check_evidence')
    op.drop_index('ix_ai_check_source_run_id', table_name='ai_check_source')
    op.drop_table('ai_check_source')
    for name in ('ix_ai_check_run_user_company_item', 'ix_ai_check_run_status',
                 'ix_ai_check_run_checklist_item_id', 'ix_ai_check_run_company_id',
                 'ix_ai_check_run_user_id'):
        op.drop_index(name, table_name='ai_check_run')
    op.drop_table('ai_check_run')
    op.drop_column('question_bank_item', 'ai_context')
    op.drop_column('checklist_item', 'ai_context')
