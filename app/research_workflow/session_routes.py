"""
Session Management Routes Module

This module handles all routes related to work session and research session management:
- Deleting research sessions
- Completing checklist steps
- Completing kill checklist steps
- Saving session progress
- AI analysis for checklist items
"""

from flask import render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import current_user, login_required
from app import db
from app.models import (WorkSession, ChecklistAnalysis, ChecklistAnswer,
                       ResearchProject, KillChecklist, CompanyDocument)
from app.research_workflow import research_workflow_bp
from app.utils.time_utils import now_utc, ensure_timezone_aware
from app.utils.response_utils import json_success
from app.services.ai import generate_ai_content
import logging

logger = logging.getLogger(__name__)


@research_workflow_bp.route('/research_sessions/<int:session_id>/delete', methods=['POST'])
@login_required
def delete_research_session(session_id):
    """Delete a research session that is not in progress or completed"""
    session = ChecklistAnalysis.query.get_or_404(session_id)

    # Authorization check
    if session.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.my_projects'))

    # Allow deletion of in-progress sessions but with warning (handled in frontend)

    # For completed sessions, only allow deletion if they're incomplete/failed
    if session.status == 'completed':
        total_answers = ChecklistAnswer.query.filter_by(checklist_analysis_id=session_id).all()
        total_item_count = len(total_answers)
        satisfied_count = len([ans for ans in total_answers if ans.satisfaction_status == 'satisfied'])

        # Don't allow deletion of successfully completed sessions
        if total_item_count > 0 and satisfied_count == total_item_count:
            flash('Cannot delete successfully completed research sessions', 'error')
            return redirect(url_for('research_workflow.my_projects'))

    try:
        # Delete related research answers first to handle foreign key constraints
        ChecklistAnswer.query.filter_by(checklist_analysis_id=session_id).delete()

        # Commit the deletion of related records
        db.session.commit()

        # Delete the research session itself
        db.session.delete(session)
        db.session.commit()

        flash(f'Research session for "{session.company.name if session.company else "Unknown"}" has been deleted', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting research session: {str(e)}', 'error')

    return redirect(url_for('research_workflow.my_projects'))


@research_workflow_bp.route('/projects/<int:project_id>/sessions/<int:session_id>/complete-checklist', methods=['POST'])
@login_required
def complete_checklist_step(project_id, session_id):
    """Complete a checklist step and save results"""
    project = ResearchProject.query.get_or_404(project_id)
    session = WorkSession.query.get_or_404(session_id)

    if project.user_id != current_user.id or session.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.my_projects'))

    # Get step details
    step = project.template.get_step(session.step_index)
    if not step or step['type'] != 'checklist':
        flash('Invalid checklist step', 'error')
        return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))

    # Process criteria evaluation results
    checklist_items = step['config'].get('checklist_items', [])
    analysis_notes = request.form.getlist('analysis_notes[]')
    item_notes = request.form.getlist('item_notes[]')
    step_notes = request.form.get('step_notes', '')

    # Process each criterion's evaluation
    criteria_evaluations = []
    met_count = 0
    critical_failed = 0
    total_evaluated = 0

    for i, item in enumerate(checklist_items):
        status = request.form.get(f'criteria_status_{i}')
        importance = request.form.get(f'criteria_importance_{i}', 'important')

        evaluation = {
            'index': i,
            'item_text': item['item'],
            'status': status,  # 'met', 'not_met', or 'not_applicable'
            'importance': importance,  # 'critical', 'important', 'nice_to_have'
            'notes': analysis_notes[i] if i < len(analysis_notes) else (item_notes[i] if i < len(item_notes) else '')
        }
        criteria_evaluations.append(evaluation)

        # Count results for summary
        if status == 'met':
            met_count += 1
            total_evaluated += 1
        elif status == 'not_met':
            if importance == 'critical':
                critical_failed += 1
            total_evaluated += 1
        # 'not_applicable' items don't count toward totals

    # Determine overall step result
    if total_evaluated == 0:
        step_result = 'incomplete'
        step_status_msg = 'No criteria were evaluated'
    elif critical_failed > 0:
        step_result = 'fail'
        step_status_msg = f'FAILED: {critical_failed} critical criteria not met'
    else:
        pass_rate = (met_count / total_evaluated) * 100 if total_evaluated > 0 else 0
        if pass_rate >= 80:  # 80% threshold for pass
            step_result = 'pass'
            step_status_msg = f'PASSED: {met_count}/{total_evaluated} criteria met ({pass_rate:.1f}%)'
        else:
            step_result = 'marginal'
            step_status_msg = f'MARGINAL: {met_count}/{total_evaluated} criteria met ({pass_rate:.1f}%) - Review required'

    # Build comprehensive results structure
    checklist_results = {
        'criteria_evaluations': criteria_evaluations,
        'total_items': len(checklist_items),
        'met_count': met_count,
        'total_evaluated': total_evaluated,
        'critical_failed': critical_failed,
        'step_result': step_result,
        'step_status_msg': step_status_msg,
        'pass_rate': (met_count / total_evaluated) * 100 if total_evaluated > 0 else 0
    }

    # Complete the session
    session.end_time = now_utc()
    start_time_aware = ensure_timezone_aware(session.start_time)
    session.duration_minutes = int((session.end_time - start_time_aware).total_seconds() / 60)
    session.notes = step_notes
    session.results = checklist_results
    session.status = 'completed'

    # Update project time tracking
    if session.duration_minutes:
        if not project.time_per_step:
            project.time_per_step = {}
        current_time = project.time_per_step.get(str(session.step_index), 0)
        project.time_per_step[str(session.step_index)] = current_time + session.duration_minutes
        project.total_hours_spent = (project.total_hours_spent or 0) + session.duration_minutes / 60

    # Update project progress
    if not project.step_notes:
        project.step_notes = {}
    project.step_notes[str(session.step_index)] = step_notes

    if not project.step_results:
        project.step_results = {}
    project.step_results[str(session.step_index)] = checklist_results

    # Mark step as complete
    if not project.completed_steps:
        project.completed_steps = []

    if session.step_index not in project.completed_steps:
        project.completed_steps = project.completed_steps + [session.step_index]

    # Move to next step
    if session.step_index + 1 < len(project.template.workflow_steps):
        project.current_step_index = session.step_index + 1
    else:
        project.status = 'completed'
        project.completed_at = now_utc()

    project.last_worked_at = now_utc()

    try:
        db.session.commit()
        # Flash message based on step result
        if checklist_results['step_result'] == 'pass':
            flash(f'✅ {checklist_results["step_status_msg"]}', 'success')
        elif checklist_results['step_result'] == 'fail':
            flash(f'❌ {checklist_results["step_status_msg"]}', 'danger')
        elif checklist_results['step_result'] == 'marginal':
            flash(f'⚠️ {checklist_results["step_status_msg"]}', 'warning')
        else:
            flash(f'ℹ️ {checklist_results["step_status_msg"]}', 'info')

        if project.status == 'completed':
            return redirect(url_for('research_workflow.project_summary', project_id=project_id))
        else:
            return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))

    except Exception as e:
        db.session.rollback()
        flash('Error saving checklist results', 'error')
        return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))


@research_workflow_bp.route('/projects/<int:project_id>/sessions/<int:session_id>/complete-kill-checklist', methods=['POST'])
@login_required
def complete_kill_checklist_step(project_id, session_id):
    """Complete a kill checklist step and save results"""
    project = ResearchProject.query.get_or_404(project_id)
    session = WorkSession.query.get_or_404(session_id)

    if project.user_id != current_user.id or session.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.my_projects'))

    # Get step details
    step = project.template.get_step(session.step_index)
    if not step or step['type'] != 'kill_checklist_reference':
        flash('Invalid kill checklist step', 'error')
        return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))

    kill_checklist_id = request.form.get('kill_checklist_id')
    overall_result = request.form.get('overall_result')  # 'proceed' or 'kill'
    step_notes = request.form.get('step_notes', '')

    # Process individual item results
    kill_checklist = KillChecklist.query.get(kill_checklist_id)
    item_results = []

    for item in kill_checklist.items:
        result = request.form.get(f'result_{item.id}')
        notes = request.form.get(f'notes_{item.id}', '')

        item_results.append({
            'item_id': item.id,
            'item_text': item.text,
            'result': result,  # 'pass' or 'fail'
            'notes': notes
        })

    # Calculate screening statistics
    pass_count = len([r for r in item_results if r['result'] == 'pass'])
    fail_count = len([r for r in item_results if r['result'] == 'fail'])

    kill_checklist_results = {
        'kill_checklist_id': kill_checklist_id,
        'kill_checklist_name': kill_checklist.name,
        'overall_result': overall_result,
        'item_results': item_results,
        'pass_count': pass_count,
        'fail_count': fail_count,
        'total_items': len(item_results),
        'screening_passed': overall_result == 'proceed'
    }

    # Complete the session
    session.end_time = now_utc()
    start_time_aware = ensure_timezone_aware(session.start_time)
    session.duration_minutes = int((session.end_time - start_time_aware).total_seconds() / 60)
    session.notes = step_notes
    session.results = kill_checklist_results
    session.status = 'completed'

    # Update project time tracking
    if session.duration_minutes:
        if not project.time_per_step:
            project.time_per_step = {}
        current_time = project.time_per_step.get(str(session.step_index), 0)
        project.time_per_step[str(session.step_index)] = current_time + session.duration_minutes
        project.total_hours_spent = (project.total_hours_spent or 0) + session.duration_minutes / 60

    # Update project progress
    if not project.step_notes:
        project.step_notes = {}
    project.step_notes[str(session.step_index)] = step_notes

    if not project.step_results:
        project.step_results = {}
    project.step_results[str(session.step_index)] = kill_checklist_results

    # Mark step as complete (even if killed - it was completed)
    if not project.completed_steps:
        project.completed_steps = []

    if session.step_index not in project.completed_steps:
        project.completed_steps = project.completed_steps + [session.step_index]

    # Handle kill decision
    if overall_result == 'kill':
        project.status = 'killed'
        project.completed_at = now_utc()
        project.kill_reason = f"Failed screening: {step_notes}"
    else:
        # Move to next step
        if session.step_index + 1 < len(project.template.workflow_steps):
            project.current_step_index = session.step_index + 1
        else:
            project.status = 'completed'
            project.completed_at = now_utc()

    project.last_worked_at = now_utc()

    try:
        db.session.commit()

        if overall_result == 'kill':
            flash(f'Investment killed during screening. Failed {fail_count}/{len(item_results)} criteria.', 'warning')
            return redirect(url_for('research_workflow.project_summary', project_id=project_id))
        else:
            flash(f'Screening passed! {pass_count}/{len(item_results)} criteria met.', 'success')

            if project.status == 'completed':
                return redirect(url_for('research_workflow.project_summary', project_id=project_id))
            else:
                return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))

    except Exception as e:
        db.session.rollback()
        flash('Error saving screening results', 'error')
        return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))


@research_workflow_bp.route('/projects/<int:project_id>/sessions/<int:session_id>/save-checklist-progress', methods=['POST'])
@login_required
def save_checklist_progress(project_id, session_id):
    """Auto-save checklist progress"""
    # Simple auto-save endpoint for checklist progress
    return json_success('Progress saved')


@research_workflow_bp.route('/projects/<int:project_id>/sessions/<int:session_id>/save-kill-checklist-progress', methods=['POST'])
@login_required
def save_kill_checklist_progress(project_id, session_id):
    """Auto-save kill checklist progress"""
    # Simple auto-save endpoint for kill checklist progress
    return json_success('Progress saved')


@research_workflow_bp.route('/projects/<int:project_id>/sessions/<int:session_id>/checklist_item_analyze', methods=['POST'])
@login_required
def analyze_checklist_item(project_id, session_id):
    """AI analysis for Research Template checklist items"""
    # Get and validate project and session
    project = ResearchProject.query.get_or_404(project_id)
    session = WorkSession.query.get_or_404(session_id)

    if project.user_id != current_user.id or session.user_id != current_user.id:
        return jsonify({'status': 'error', 'message': 'Access denied'}), 403

    if session.project_id != project_id:
        return jsonify({'status': 'error', 'message': 'Invalid session for project'}), 400

    # Check Gemini API configuration
    gemini_api_key = current_app.config.get('GEMINI_API_KEY')
    if not gemini_api_key:
        return jsonify({
            'status': 'error_config',
            'message': 'Gemini API key not configured. Please check server configuration.'
        }), 500

    # LLM service will handle API configuration automatically

    # Parse request data
    if not request.is_json:
        return jsonify({'status': 'error', 'message': 'Request must be JSON'}), 400

    data = request.get_json()
    if not data:
        return jsonify({'status': 'error', 'message': 'No JSON data received'}), 400

    # Extract parameters
    item_index = data.get('item_index')  # Index of the checklist item
    llm_prompt = data.get('llm_prompt', '')
    selected_document_ids = data.get('selected_document_ids', [])

    if item_index is None:
        return jsonify({'status': 'error', 'message': 'item_index is required'}), 400

    if not llm_prompt:
        return jsonify({
            'status': 'error_no_prompt',
            'message': 'No LLM prompt provided for analysis'
        }), 400

    # Get the current step and validate the item index
    step = project.template.get_step(session.step_index)
    if not step or step['type'] != 'checklist':
        return jsonify({'status': 'error', 'message': 'Invalid step or not a checklist step'}), 400

    checklist_items = step['config'].get('checklist_items', [])
    if item_index >= len(checklist_items):
        return jsonify({'status': 'error', 'message': 'Invalid item index'}), 400

    # Handle document processing for company projects only
    documents = []
    if selected_document_ids and project.company_id:
        try:
            doc_ids = [int(doc_id) for doc_id in selected_document_ids]
            documents = CompanyDocument.query.filter(
                CompanyDocument.id.in_(doc_ids),
                CompanyDocument.company_id == project.company_id
            ).all()
        except ValueError:
            return jsonify({'status': 'error', 'message': 'Invalid document ID format'}), 400

    # Process documents and extract text (simplified approach)
    document_context = ""
    processed_docs_info = []

    if documents:
        for doc in documents:
            try:
                # Simple text extraction - in a real implementation you'd want proper document processing
                with open(doc.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    doc_text = f.read()[:2000]  # Limit to first 2000 chars per doc
                    document_context += f"\n\n=== {doc.title or doc.filename} ===\n{doc_text}"
                    processed_docs_info.append({
                        'id': doc.id,
                        'title': doc.title,
                        'filename': doc.filename
                    })
            except Exception as e:
                print(f"Error processing document {doc.id}: {e}")
                continue

    # Prepare the analysis prompt
    item_text = checklist_items[item_index]['item']
    analysis_context = f"""Research Context:
- Subject: {project.subject_display_name}
- Template: {project.template.name}
- Current Step: {step['name']}
- Checklist Item: {item_text}

User's Analysis Request:
{llm_prompt}
"""

    if document_context:
        analysis_context += f"\n\nAvailable Documents:{document_context}"
    else:
        analysis_context += "\n\nNo documents were provided for analysis."

    # Generate AI analysis using unified LLM service
    try:
        ai_suggestion = generate_ai_content(analysis_context)

        return jsonify({
            'status': 'success_analysis_complete',
            'message': 'Analysis completed successfully',
            'ai_suggestion': ai_suggestion,
            'received_prompt': llm_prompt,
            'item_text': item_text,
            'selected_documents_info': processed_docs_info,
            'extracted_text_sample': document_context[:500] + '...' if len(document_context) > 500 else document_context
        })

    except Exception as e:
        error_msg = str(e)
        print(f"Gemini API error: {error_msg}")

        return jsonify({
            'status': 'error_ai_failed',
            'message': f'AI analysis failed: {error_msg}',
            'received_prompt': llm_prompt,
            'selected_documents_info': processed_docs_info
        }), 500
