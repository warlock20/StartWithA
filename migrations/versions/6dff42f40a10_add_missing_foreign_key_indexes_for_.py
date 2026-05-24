"""add missing foreign key indexes for performance

Revision ID: 6dff42f40a10
Revises: e8b177b851bd
Create Date: 2026-05-24 20:25:10.513268

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '6dff42f40a10'
down_revision = 'e8b177b851bd'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('ai_insight', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_ai_insight_company_id'), ['company_id'], unique=False)

    with op.batch_alter_table('background_task', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_background_task_project_id'), ['project_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_background_task_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('checklist', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_checklist_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('checklist_analysis', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_checklist_analysis_checklist_id'), ['checklist_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_checklist_analysis_company_id'), ['company_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_checklist_analysis_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('checklist_answer', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_checklist_answer_checklist_analysis_id'), ['checklist_analysis_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_checklist_answer_checklist_item_id'), ['checklist_item_id'], unique=False)

    with op.batch_alter_table('checklist_item', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_checklist_item_checklist_id'), ['checklist_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_checklist_item_parent_id'), ['parent_id'], unique=False)

    with op.batch_alter_table('company', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_company_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('company_resource', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_company_resource_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('decision_journal', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_decision_journal_company_id'), ['company_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_decision_journal_project_id'), ['project_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_decision_journal_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('destination_checkpoint', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_destination_checkpoint_company_id'), ['company_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_destination_checkpoint_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('document_imports', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_document_imports_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('financial_data', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_financial_data_company_id'), ['company_id'], unique=False)

    with op.batch_alter_table('idea_pipeline', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_idea_pipeline_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('journal_attachment', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_journal_attachment_journal_entry_id'), ['journal_entry_id'], unique=False)

    with op.batch_alter_table('journal_entry', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_journal_entry_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('journal_template', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_journal_template_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('kill_answer', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_kill_answer_criterion_id'), ['criterion_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_kill_answer_kill_session_id'), ['kill_session_id'], unique=False)

    with op.batch_alter_table('kill_checklist', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_kill_checklist_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('kill_checklist_suggestion', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_kill_checklist_suggestion_kill_checklist_id'), ['kill_checklist_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_kill_checklist_suggestion_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('kill_criterion', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_kill_criterion_kill_checklist_id'), ['kill_checklist_id'], unique=False)

    with op.batch_alter_table('kill_session', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_kill_session_idea_id'), ['idea_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_kill_session_kill_checklist_id'), ['kill_checklist_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_kill_session_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('learning_note', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_learning_note_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('qualitative_analysis', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_qualitative_analysis_company_id'), ['company_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_qualitative_analysis_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('question_bank_item', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_question_bank_item_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('research_project', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_research_project_company_id'), ['company_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_research_project_idea_id'), ['idea_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_research_project_template_id'), ['template_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_research_project_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('research_template', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_research_template_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('scuttlebutt_analysis', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_scuttlebutt_analysis_company_id'), ['company_id'], unique=False)

    with op.batch_alter_table('sector_analysis', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_sector_analysis_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('template_step', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_template_step_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('thesis_evolution', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_thesis_evolution_company_id'), ['company_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_thesis_evolution_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('work_session', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_work_session_project_id'), ['project_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_work_session_user_id'), ['user_id'], unique=False)


def downgrade():
    with op.batch_alter_table('work_session', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_work_session_user_id'))
        batch_op.drop_index(batch_op.f('ix_work_session_project_id'))

    with op.batch_alter_table('thesis_evolution', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_thesis_evolution_user_id'))
        batch_op.drop_index(batch_op.f('ix_thesis_evolution_company_id'))

    with op.batch_alter_table('template_step', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_template_step_user_id'))

    with op.batch_alter_table('sector_analysis', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_sector_analysis_user_id'))

    with op.batch_alter_table('scuttlebutt_analysis', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_scuttlebutt_analysis_company_id'))

    with op.batch_alter_table('research_template', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_research_template_user_id'))

    with op.batch_alter_table('research_project', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_research_project_user_id'))
        batch_op.drop_index(batch_op.f('ix_research_project_template_id'))
        batch_op.drop_index(batch_op.f('ix_research_project_idea_id'))
        batch_op.drop_index(batch_op.f('ix_research_project_company_id'))

    with op.batch_alter_table('question_bank_item', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_question_bank_item_user_id'))

    with op.batch_alter_table('qualitative_analysis', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_qualitative_analysis_user_id'))
        batch_op.drop_index(batch_op.f('ix_qualitative_analysis_company_id'))

    with op.batch_alter_table('learning_note', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_learning_note_user_id'))

    with op.batch_alter_table('kill_session', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_kill_session_user_id'))
        batch_op.drop_index(batch_op.f('ix_kill_session_kill_checklist_id'))
        batch_op.drop_index(batch_op.f('ix_kill_session_idea_id'))

    with op.batch_alter_table('kill_criterion', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_kill_criterion_kill_checklist_id'))

    with op.batch_alter_table('kill_checklist_suggestion', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_kill_checklist_suggestion_user_id'))
        batch_op.drop_index(batch_op.f('ix_kill_checklist_suggestion_kill_checklist_id'))

    with op.batch_alter_table('kill_checklist', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_kill_checklist_user_id'))

    with op.batch_alter_table('kill_answer', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_kill_answer_kill_session_id'))
        batch_op.drop_index(batch_op.f('ix_kill_answer_criterion_id'))

    with op.batch_alter_table('journal_template', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_journal_template_user_id'))

    with op.batch_alter_table('journal_entry', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_journal_entry_user_id'))

    with op.batch_alter_table('journal_attachment', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_journal_attachment_journal_entry_id'))

    with op.batch_alter_table('idea_pipeline', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_idea_pipeline_user_id'))

    with op.batch_alter_table('financial_data', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_financial_data_company_id'))

    with op.batch_alter_table('document_imports', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_document_imports_user_id'))

    with op.batch_alter_table('destination_checkpoint', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_destination_checkpoint_user_id'))
        batch_op.drop_index(batch_op.f('ix_destination_checkpoint_company_id'))

    with op.batch_alter_table('decision_journal', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_decision_journal_user_id'))
        batch_op.drop_index(batch_op.f('ix_decision_journal_project_id'))
        batch_op.drop_index(batch_op.f('ix_decision_journal_company_id'))

    with op.batch_alter_table('company_resource', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_company_resource_user_id'))

    with op.batch_alter_table('company', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_company_user_id'))

    with op.batch_alter_table('checklist_item', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_checklist_item_parent_id'))
        batch_op.drop_index(batch_op.f('ix_checklist_item_checklist_id'))

    with op.batch_alter_table('checklist_answer', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_checklist_answer_checklist_item_id'))
        batch_op.drop_index(batch_op.f('ix_checklist_answer_checklist_analysis_id'))

    with op.batch_alter_table('checklist_analysis', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_checklist_analysis_user_id'))
        batch_op.drop_index(batch_op.f('ix_checklist_analysis_company_id'))
        batch_op.drop_index(batch_op.f('ix_checklist_analysis_checklist_id'))

    with op.batch_alter_table('checklist', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_checklist_user_id'))

    with op.batch_alter_table('background_task', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_background_task_user_id'))
        batch_op.drop_index(batch_op.f('ix_background_task_project_id'))

    with op.batch_alter_table('ai_insight', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_ai_insight_company_id'))
