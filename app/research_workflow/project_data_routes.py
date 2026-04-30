"""
Project Data Routes Module

This module handles all routes related to project content and data including:
- Viewing project notes and summaries
- Saving project decisions
- Adding findings (green/red flags)
- Updating investment thesis
"""

import traceback
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user, login_required
from app import db
from app.models import ResearchProject, ChecklistAnalysis
from app.models.research import FreeResearchQuestion
from app.research_workflow import research_workflow_bp
from app.utils.time_utils import now_utc
from app.utils.response_utils import json_success, json_error, json_unauthorized
from app.services.export_service import resolve_checklist_id
from app.services.research_quality import calculate_research_quality

@research_workflow_bp.route('/projects/<int:project_id>/summary')
@login_required
def project_summary(project_id):
    """Show summary and decision page for completed project"""
    project = ResearchProject.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.my_projects'))

    # Compile all notes with step metadata
    all_notes = []
    checklist_analyses = {}  # Map step_index -> analysis_id

    for step_index_str, notes in (project.step_notes or {}).items():
        step_index = int(step_index_str)
        step = project.template.get_step(step_index)
        if step and notes:
            all_notes.append({
                'step_index': step_index,
                'step_name': step.get('name', f'Step {step_index + 1}'),
                'step_type': step.get('type', 'research'),
                'notes': notes
            })

            # Find checklist analysis if this is a checklist step
            if step.get('type') == 'checklist' and project.company_id:
                checklist_id = resolve_checklist_id(project, step_index, step)
                if checklist_id:
                    analysis = ChecklistAnalysis.query.filter_by(
                        user_id=current_user.id,
                        checklist_id=checklist_id,
                        company_id=project.company_id
                    ).order_by(ChecklistAnalysis.start_date.desc()).first()
                    if analysis:
                        checklist_analyses[step_index] = analysis.id

    # Sort by step index
    all_notes.sort(key=lambda x: x['step_index'])

    # Load free research questions for free_research steps
    free_research_questions = {}
    for note in all_notes:
        if note['step_type'] == 'free_research':
            questions = FreeResearchQuestion.query.filter_by(
                project_id=project_id,
                step_index=note['step_index']
            ).order_by(FreeResearchQuestion.order_index).all()
            free_research_questions[note['step_index']] = questions

    # ═══════════════════════════════════════════════════════════════
    # RESEARCH QUALITY SCORE CALCULATION
    # ═══════════════════════════════════════════════════════════════
    quality_score = None
    try:
        quality_score = calculate_research_quality(research_project_id=project.id)
    except Exception as e:
        print(f"[AI] ✗ Error calculating quality score: {e}")
        print(traceback.format_exc())
    # ═══════════════════════════════════════════════════════════════

    return render_template('project_summary.html',
                          title=f"Summary: {project.subject_display_name}",
                          project=project,
                          all_notes=all_notes,
                          checklist_analyses=checklist_analyses,
                          free_research_questions=free_research_questions,
                          quality_score=quality_score)


@research_workflow_bp.route('/projects/<int:project_id>/save-decision', methods=['POST'])
@login_required
def save_project_decision(project_id):
    """Save investment decision for a project (supports both form and AJAX)"""
    project = ResearchProject.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        if request.headers.get('Content-Type') == 'application/x-www-form-urlencoded':
            return json_unauthorized('Access denied')
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.my_projects'))

    try:
        # Get form data (works for both form and AJAX)
        project.last_worked_at = now_utc()
        decision = request.form.get('decision')  # invest, pass, watchlist
        decision_summary = request.form.get('decision_summary', '').strip()
        confidence = request.form.get('confidence') or request.form.get('decision_confidence')
        decision_confidence = int(confidence) if confidence else None

        green_flags_raw = request.form.get('green_flags', '')
        red_flags_raw = request.form.get('red_flags', '')

        # Validate decision
        if decision not in ['invest', 'pass', 'watchlist']:
            if request.headers.get('Content-Type') == 'application/x-www-form-urlencoded':
                return json_error('Invalid decision type')
            flash('Invalid decision type', 'error')
            return redirect(url_for('research_workflow.project_summary', project_id=project_id))

        # Update project
        project.decision = decision
        project.decision_summary = decision_summary
        project.decision_confidence = decision_confidence
        project.decision_date = now_utc()
        project.green_flags = [f.strip() for f in green_flags_raw.split('\n') if f.strip()]
        project.red_flags = [f.strip() for f in red_flags_raw.split('\n') if f.strip()]

        # Mark as completed if not already
        if project.status != 'completed':
            project.status = 'completed'
            project.completed_at = now_utc()

        db.session.commit()

        # AJAX response
        if request.headers.get('Content-Type') == 'application/x-www-form-urlencoded':
            return jsonify({
                'success': True,
                'decision': decision,
                'message': f'Decision saved: {decision.title()}'
            })

        # Traditional form submission - redirect with flash
        if decision == 'invest':
            flash(f'Decision recorded: Investing in {project.subject_display_name}! 🎯', 'success')
            if project.company_id:
                flash('Add a transaction to start tracking your investment.', 'info')
                return redirect(url_for('portfolio.add_transaction', company_id=project.company_id))
        elif decision == 'pass':
            flash(f'Decision recorded: Passing on {project.subject_display_name}. Good discipline! 💪', 'info')
        else:
            flash(f'Decision recorded: {project.subject_display_name} added to watchlist. 👀', 'info')

        return redirect(url_for('research_workflow.my_projects'))

    except Exception as e:
        db.session.rollback()
        if request.headers.get('Content-Type') == 'application/x-www-form-urlencoded':
            return json_error(str(e), status_code=500)
        flash(f'Error saving decision: {str(e)}', 'error')
        return redirect(url_for('research_workflow.project_summary', project_id=project_id))


@research_workflow_bp.route('/projects/<int:project_id>/add-finding', methods=['POST'])
@login_required
def add_finding(project_id):
    """Add a green or red flag finding to a project"""
    project = ResearchProject.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        return json_unauthorized('Access denied')

    try:
        if request.is_json:
            data = request.get_json()
            finding_type = data.get('type')  # 'green' or 'red'
            finding_text = data.get('text', '').strip()
        else:
            # Handle standard form submission
            finding_type = request.form.get('finding_type')
            finding_text = request.form.get('finding_text', '').strip()
        
        # Normalize types (convert green_flag to green, etc. if needed)
        if 'green' in finding_type: finding_type = 'green'
        if 'red' in finding_type: finding_type = 'red'
        
        if not finding_text:
            return json_error('Finding text is required')

        if not finding_text:
            return json_error('Finding text is required')

        if finding_type == 'green':
            project.green_flags = (project.green_flags or []) + [finding_text]
        elif finding_type == 'red':
            project.red_flags = (project.red_flags or []) + [finding_text]
        else:
            return json_error('Invalid finding type')
        
        project.last_worked_at = now_utc()
        db.session.commit()
        
        # If it was a form submisison, redirect back. If AJAX, return JSON.
        if not request.is_json:
            flash(f'{finding_type.capitalize()} flag added!', 'success')
            return redirect(url_for('research_workflow.project_dashboard', project_id=project.id))
            
        return json_success(f'{finding_type.capitalize()} flag added')

    except Exception as e:
        db.session.rollback()
        return json_error(str(e), status_code=500)


@research_workflow_bp.route('/projects/<int:project_id>/remove-finding', methods=['POST'])
@login_required
def remove_finding(project_id):
    """Remove a finding from a project"""
    project = ResearchProject.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        return json_unauthorized('Access denied')
    
    project.last_worked_at = now_utc()
    try:
        data = request.get_json()
        finding_type = data.get('type')
        finding_index = data.get('index', type=int)

        if finding_type == 'green' and project.green_flags:
            if 0 <= finding_index < len(project.green_flags):
                flags = list(project.green_flags)
                flags.pop(finding_index)
                project.green_flags = flags
        elif finding_type == 'red' and project.red_flags:
            if 0 <= finding_index < len(project.red_flags):
                flags = list(project.red_flags)
                flags.pop(finding_index)
                project.red_flags = flags

        db.session.commit()
        return json_success('Finding removed')

    except Exception as e:
        db.session.rollback()
        return json_error(str(e), status_code=500)


@research_workflow_bp.route('/projects/<int:project_id>/update-thesis', methods=['POST'])
@login_required
def update_thesis(project_id):
    """Update the evolving investment thesis"""
    project = ResearchProject.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        return json_unauthorized('Access denied')

    try:
        # Support both form POST and JSON
        project.last_worked_at = now_utc()
        if request.is_json:
            thesis = request.get_json().get('thesis', '').strip()
        else:
            thesis = request.form.get('investment_thesis', '').strip()

        project.investment_thesis = thesis
        db.session.commit()

        if request.is_json:
            return json_success('Thesis updated')
        flash('Thesis updated', 'success')
        return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))

    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return json_error(str(e), status_code=500)
        flash(f'Error updating thesis: {str(e)}', 'error')
        return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))


@research_workflow_bp.route('/projects/<int:project_id>/update-summary', methods=['POST'])
@login_required
def update_summary(project_id):
    """Update the project summary"""
    project = ResearchProject.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        return json_unauthorized('Access denied')

    try:
        data = request.get_json()
        summary = data.get('summary', '').strip()

        project.summary = summary
        project.last_worked_at = now_utc()
        db.session.commit()

        return json_success('Summary updated')

    except Exception as e:
        db.session.rollback()
        return json_error(str(e), status_code=500)