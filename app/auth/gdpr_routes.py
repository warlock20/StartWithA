"""
GDPR / DSGVO Compliance Routes

Implements user data rights under GDPR:
- Art. 6(1)(a): Consent management (AI features)
- Art. 15: Right of access (data export)
- Art. 17: Right to erasure (account deletion)
"""

import json
import logging

from flask import request, redirect, url_for, flash, jsonify, Response
from flask_login import login_required, logout_user, current_user
from app import db, limiter
from app.auth import auth_bp
from app.constants import RATELIMIT_AUTH
from app.utils.time_utils import now_utc
from app.utils.response_utils import serialize_model_to_dict
from app.utils.db_utils import safe_db_transaction
from app.utils.audit_logger import log_consent_change, log_data_export, log_account_deletion

logger = logging.getLogger(__name__)


def _collect_user_data(user):
    """
    Collect all personal data for a user across all tables.
    Returns a structured dictionary suitable for JSON export.
    GDPR Art. 15 - Right of access.
    """
    from app.models import (
        Company, CompanyDocument, QualitativeAnalysis,
        Checklist, QuestionBankItem, DestinationCheckpoint, DocumentImport,
        IdeaPipeline, KillChecklist, KillSession, KillChecklistSuggestion,
        IdeaSourceAnalysis, MistakeLog,
        ChecklistAnalysis, ResearchTemplate, ResearchProject, WorkSession,
        TemplateStep, ResearchMetrics, ResearchLog, FreeResearchQuestion,
        ResearchSettings,
        Sector, SectorAnalysis,
        DecisionJournal, JournalEntry, ThesisEvolution, LearningNote,
        JournalTemplate, WeeklyReview, InvestmentPostMortem, LearningPath,
        PatternRecognition,
        Transaction, PortfolioPosition,
        ResearchOutcome, AIInsight,
        PromptUsageLog,
        AIResearchFeedback,
        BiasCheckResult,
        PortfolioUIInsight,
        UserInvestmentProfile,
    )

    exclude_sensitive = ['password_hash']

    data = {
        'export_metadata': {
            'exported_at': now_utc().isoformat(),
            'user_id': user.id,
            'format_version': '1.0',
            'description': 'Complete personal data export per GDPR Art. 15',
        },

        'profile': serialize_model_to_dict(user, exclude=exclude_sensitive),

        'favorites': [c.id for c in user.favorites.all()],
    }

    # Map of section name -> (Model, filter_expression)
    # All models with user_id foreign key
    sections = [
        ('companies', Company, Company.user_id == user.id),
        ('company_documents', CompanyDocument, CompanyDocument.user_id == user.id),
        ('qualitative_analyses', QualitativeAnalysis, QualitativeAnalysis.user_id == user.id),
        ('checklists', Checklist, Checklist.user_id == user.id),
        ('question_bank_items', QuestionBankItem, QuestionBankItem.user_id == user.id),
        ('destination_checkpoints', DestinationCheckpoint, DestinationCheckpoint.user_id == user.id),
        ('document_imports', DocumentImport, DocumentImport.user_id == user.id),
        ('idea_pipeline', IdeaPipeline, IdeaPipeline.user_id == user.id),
        ('kill_checklists', KillChecklist, KillChecklist.user_id == user.id),
        ('kill_sessions', KillSession, KillSession.user_id == user.id),
        ('kill_checklist_suggestions', KillChecklistSuggestion, KillChecklistSuggestion.user_id == user.id),
        ('idea_source_analyses', IdeaSourceAnalysis, IdeaSourceAnalysis.user_id == user.id),
        ('mistake_logs', MistakeLog, MistakeLog.user_id == user.id),
        ('research_sessions', ChecklistAnalysis, ChecklistAnalysis.user_id == user.id),
        ('research_templates', ResearchTemplate, ResearchTemplate.user_id == user.id),
        ('research_projects', ResearchProject, ResearchProject.user_id == user.id),
        ('work_sessions', WorkSession, WorkSession.user_id == user.id),
        ('template_steps', TemplateStep, TemplateStep.user_id == user.id),
        ('research_logs', ResearchLog, ResearchLog.user_id == user.id),
        ('free_research_questions', FreeResearchQuestion, FreeResearchQuestion.user_id == user.id),
        ('sectors', Sector, Sector.user_id == user.id),
        ('sector_analyses', SectorAnalysis, SectorAnalysis.user_id == user.id),
        ('decision_journals', DecisionJournal, DecisionJournal.user_id == user.id),
        ('journal_entries', JournalEntry, JournalEntry.user_id == user.id),
        ('thesis_evolutions', ThesisEvolution, ThesisEvolution.user_id == user.id),
        ('learning_notes', LearningNote, LearningNote.user_id == user.id),
        ('journal_templates', JournalTemplate, JournalTemplate.user_id == user.id),
        ('weekly_reviews', WeeklyReview, WeeklyReview.user_id == user.id),
        ('postmortems', InvestmentPostMortem, InvestmentPostMortem.user_id == user.id),
        ('learning_paths', LearningPath, LearningPath.user_id == user.id),
        ('patterns', PatternRecognition, PatternRecognition.user_id == user.id),
        ('transactions', Transaction, Transaction.user_id == user.id),
        ('portfolio_positions', PortfolioPosition, PortfolioPosition.user_id == user.id),
        ('ai_research_feedback', AIResearchFeedback, AIResearchFeedback.user_id == user.id),
        ('ai_insights', AIInsight, AIInsight.user_id == user.id),
        ('research_outcomes', ResearchOutcome, ResearchOutcome.user_id == user.id),
        ('prompt_usage_logs', PromptUsageLog, PromptUsageLog.user_id == user.id),
        ('bias_check_results', BiasCheckResult, BiasCheckResult.user_id == user.id),
        ('portfolio_insights', PortfolioUIInsight, PortfolioUIInsight.user_id == user.id),
    ]

    for section_name, model, filter_expr in sections:
        try:
            records = model.query.filter(filter_expr).all()
            data[section_name] = [serialize_model_to_dict(r) for r in records]
        except Exception:
            data[section_name] = []

    # Single-record sections (uselist=False or unique constraint)
    for section_name, model in [
        ('research_metrics', ResearchMetrics),
        ('research_settings', ResearchSettings),
        ('investment_profile', UserInvestmentProfile),
    ]:
        try:
            record = model.query.filter_by(user_id=user.id).first()
            data[section_name] = serialize_model_to_dict(record) if record else None
        except Exception:
            data[section_name] = None

    return data


@auth_bp.route('/account/ai-consent', methods=['POST'])
@login_required
def grant_ai_consent():
    """
    GDPR Art. 6(1)(a) - Record user consent for AI feature data processing.
    Called when user accepts the AI consent modal.
    """
    try:
        current_user.ai_consent_given = True
        current_user.ai_consent_date = now_utc()
        db.session.commit()
        log_consent_change(current_user.id, 'ai_features', granted=True)
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        logger.exception(f"AI consent grant failed for user {current_user.id}: {e}")
        return jsonify({'success': False, 'error': 'Failed to save consent'}), 500


@auth_bp.route('/account/ai-consent/revoke', methods=['POST'])
@login_required
def revoke_ai_consent():
    """
    GDPR Art. 7(3) - Withdraw consent for AI feature data processing.
    """
    try:
        current_user.ai_consent_given = False
        db.session.commit()
        log_consent_change(current_user.id, 'ai_features', granted=False)
        flash('AI feature consent revoked. AI features are now disabled.', 'info')
        return redirect(url_for('auth.account_settings'))
    except Exception as e:
        db.session.rollback()
        logger.exception(f"AI consent revoke failed for user {current_user.id}: {e}")
        flash('Error revoking consent. Please try again.', 'error')
        return redirect(url_for('auth.account_settings'))


@auth_bp.route('/account/ai-consent/status')
@login_required
def ai_consent_status():
    """Check if user has given AI consent. Used by JS before triggering AI features."""
    return jsonify({
        'consented': current_user.ai_consent_given,
        'consent_date': current_user.ai_consent_date.isoformat() if current_user.ai_consent_date else None
    })


@auth_bp.route('/account/export-data', methods=['POST'])
@login_required
@limiter.limit(RATELIMIT_AUTH)
def export_data():
    """
    GDPR Art. 15 - Right of access / Data portability (Art. 20).
    Export all user data as a downloadable JSON file.
    """
    try:
        user_data = _collect_user_data(current_user)

        log_data_export(current_user.id)
        json_str = json.dumps(user_data, indent=2, ensure_ascii=False, default=str)

        filename = f"data_export_{current_user.username or current_user.id}_{now_utc().strftime('%Y%m%d')}.json"

        return Response(
            json_str,
            mimetype='application/json',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )

    except Exception as e:
        logger.exception(f"Data export failed for user {current_user.id}: {e}")
        flash('Error exporting data. Please try again or contact support.', 'error')
        return redirect(url_for('auth.account_settings'))


@auth_bp.route('/account/delete', methods=['POST'])
@login_required
@limiter.limit(RATELIMIT_AUTH)
def delete_account():
    """
    GDPR Art. 17 - Right to erasure ("right to be forgotten").
    Permanently delete all user data and the account itself.
    Requires confirmation via form field.
    """
    confirmation = request.form.get('confirm_delete', '').strip()

    if confirmation != 'DELETE':
        flash('Account deletion requires typing DELETE to confirm.', 'error')
        return redirect(url_for('auth.account_settings'))

    try:
        user_id = current_user.id

        from app.models import (
            Company, CompanyDocument, QualitativeAnalysis,
            Checklist, ChecklistItem, QuestionBankItem, DestinationCheckpoint,
            DocumentImport, ChecklistAnalysis, ChecklistAnswer,
            IdeaPipeline, KillChecklist, KillCriterion, KillSession, KillAnswer,
            KillChecklistSuggestion, IdeaSourceAnalysis, MistakeLog,
            ResearchTemplate, ResearchProject, WorkSession, TemplateStep,
            ResearchMetrics, ResearchLog, FreeResearchQuestion, ResearchSettings,
            Sector, SectorAnalysis,
            DecisionJournal, JournalEntry, JournalAttachment, ThesisEvolution,
            LearningNote, JournalTemplate, WeeklyReview, InvestmentPostMortem,
            LearningPath, PatternRecognition,
            Transaction, PortfolioPosition,
            BackgroundTask,
            ResearchOutcome, AIInsight, EmbeddingStore, MLPredictionLog,
            UserInvestmentProfile,
            PromptUsageLog,
            AIResearchFeedback,
            BiasCheckResult,
            PortfolioUIInsight,
            favorite_companies,
            User,
        )

        with safe_db_transaction(db.session):
            # AI & analytics data
            AIResearchFeedback.query.filter_by(user_id=user_id).delete()
            PromptUsageLog.query.filter_by(user_id=user_id).delete()
            BiasCheckResult.query.filter_by(user_id=user_id).delete()
            AIInsight.query.filter_by(user_id=user_id).delete()
            ResearchOutcome.query.filter_by(user_id=user_id).delete()
            EmbeddingStore.query.filter_by(user_id=user_id).delete()
            MLPredictionLog.query.filter_by(user_id=user_id).delete()
            PortfolioUIInsight.query.filter_by(user_id=user_id).delete()
            BackgroundTask.query.filter_by(user_id=user_id).delete()

            # Journal & learning data
            PatternRecognition.query.filter_by(user_id=user_id).delete()
            LearningPath.query.filter_by(user_id=user_id).delete()
            InvestmentPostMortem.query.filter_by(user_id=user_id).delete()
            WeeklyReview.query.filter_by(user_id=user_id).delete()
            LearningNote.query.filter_by(user_id=user_id).delete()
            ThesisEvolution.query.filter_by(user_id=user_id).delete()
            JournalTemplate.query.filter_by(user_id=user_id).delete()

            # Journal entries (with attachments)
            journal_entries = JournalEntry.query.filter_by(user_id=user_id).all()
            for entry in journal_entries:
                JournalAttachment.query.filter_by(journal_entry_id=entry.id).delete()
            JournalEntry.query.filter_by(user_id=user_id).delete()
            DecisionJournal.query.filter_by(user_id=user_id).delete()

            MistakeLog.query.filter_by(user_id=user_id).delete()

            # Research data
            FreeResearchQuestion.query.filter_by(user_id=user_id).delete()
            ResearchLog.query.filter_by(user_id=user_id).delete()
            ResearchMetrics.query.filter_by(user_id=user_id).delete()
            ResearchSettings.query.filter_by(user_id=user_id).delete()
            WorkSession.query.filter_by(user_id=user_id).delete()
            TemplateStep.query.filter_by(user_id=user_id).delete()

            # Research sessions (with answers)
            sessions = ChecklistAnalysis.query.filter_by(user_id=user_id).all()
            for session in sessions:
                ChecklistAnswer.query.filter_by(analysis_id=session.id).delete()
            ChecklistAnalysis.query.filter_by(user_id=user_id).delete()

            ResearchProject.query.filter_by(user_id=user_id).delete()
            ResearchTemplate.query.filter_by(user_id=user_id).delete()

            # Kill checklists (with criteria, sessions, answers)
            kill_checklists = KillChecklist.query.filter_by(user_id=user_id).all()
            for kc in kill_checklists:
                kill_sessions_list = KillSession.query.filter_by(kill_checklist_id=kc.id).all()
                for ks in kill_sessions_list:
                    KillAnswer.query.filter_by(session_id=ks.id).delete()
                KillSession.query.filter_by(kill_checklist_id=kc.id).delete()
                KillCriterion.query.filter_by(kill_checklist_id=kc.id).delete()
            KillChecklistSuggestion.query.filter_by(user_id=user_id).delete()
            KillChecklist.query.filter_by(user_id=user_id).delete()

            # Idea pipeline & source analyses
            IdeaSourceAnalysis.query.filter_by(user_id=user_id).delete()
            IdeaPipeline.query.filter_by(user_id=user_id).delete()

            # Portfolio data
            Transaction.query.filter_by(user_id=user_id).delete()
            PortfolioPosition.query.filter_by(user_id=user_id).delete()

            # Sector data
            SectorAnalysis.query.filter_by(user_id=user_id).delete()
            Sector.query.filter_by(user_id=user_id).delete()

            # Checklist data (items are children of checklists)
            checklists = Checklist.query.filter_by(user_id=user_id).all()
            for cl in checklists:
                ChecklistItem.query.filter_by(checklist_id=cl.id).delete()
            Checklist.query.filter_by(user_id=user_id).delete()
            QuestionBankItem.query.filter_by(user_id=user_id).delete()
            DestinationCheckpoint.query.filter_by(user_id=user_id).delete()
            DocumentImport.query.filter_by(user_id=user_id).delete()

            # Company data
            CompanyDocument.query.filter_by(user_id=user_id).delete()
            QualitativeAnalysis.query.filter_by(user_id=user_id).delete()

            # Favorites (association table)
            db.session.execute(
                favorite_companies.delete().where(favorite_companies.c.user_id == user_id)
            )

            Company.query.filter_by(user_id=user_id).delete()

            # User config
            UserInvestmentProfile.query.filter_by(user_id=user_id).delete()

            # Finally, delete the user
            user = User.query.get(user_id)
            if user:
                db.session.delete(user)

        # Log out the now-deleted user
        logout_user()

        log_account_deletion(user_id)
        flash('Your account and all associated data have been permanently deleted.', 'info')
        return redirect(url_for('main.index'))

    except Exception as e:
        logger.exception(f"Account deletion failed for user {current_user.id}: {e}")
        flash('Error deleting account. Please try again or contact support.', 'error')
        return redirect(url_for('auth.account_settings'))
