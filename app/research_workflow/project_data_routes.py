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
from app.models import ResearchTemplate, ResearchProject, Sector, ChecklistAnalysis, ChecklistAnswer
from app.research_workflow import research_workflow_bp
from app.services.too_hard_service import TooHardBasketService
from app.utils.time_utils import now_utc


@research_workflow_bp.route('/projects/<int:project_id>/notes')
@login_required
def view_project_notes(project_id):
    """View all research notes for a project"""
    project = ResearchProject.query.get_or_404(project_id)

    # Authorization check
    if project.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.my_projects'))

    # Get all step notes
    step_notes = project.step_notes or {}

    # Get template steps for context
    template_steps = project.template.workflow_steps if project.template else []

    # Combine notes with step information
    notes_with_context = []
    for step_index, notes in step_notes.items():
        step_idx = int(step_index)
        step_name = "Unknown Step"
        if step_idx < len(template_steps):
            step_name = template_steps[step_idx].get('name', f'Step {step_idx + 1}')

        notes_with_context.append({
            'step_index': step_idx,
            'step_name': step_name,
            'notes': notes
        })

    # Sort by step index
    notes_with_context.sort(key=lambda x: x['step_index'])

    return render_template('project_notes.html',
                          title=f"Research Notes - {project.subject_display_name}",
                          project=project,
                          notes_with_context=notes_with_context)


@research_workflow_bp.route('/projects/<int:project_id>/summary')
@login_required
def project_summary(project_id):
    """Show summary and decision page for completed project"""
    project = ResearchProject.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.my_projects'))

    # Compile all notes and findings
    all_notes = []
    for step_index, notes in (project.step_notes or {}).items():
        step = project.template.get_step(int(step_index))
        if step and notes:
            all_notes.append({
                'step_name': step['name'],
                'notes': notes
            })

    # ═══════════════════════════════════════════════════════════════
    # RESEARCH QUALITY SCORE CALCULATION
    # Calculate and display quality score for completed research
    # ═══════════════════════════════════════════════════════════════
    quality_score = None
    try:
        from app.services.research_quality import calculate_research_quality
        quality_score = calculate_research_quality(research_project_id=project.id)
    except Exception as e:
        print(f"[AI] ✗ Error calculating quality score: {e}")
        print(traceback.format_exc())
    # ═══════════════════════════════════════════════════════════════

    return render_template('project_summary.html',
                          title=f"Summary: {project.subject_display_name}",
                          project=project,
                          all_notes=all_notes,
                          quality_score=quality_score)


@research_workflow_bp.route('/projects/<int:project_id>/save-decision', methods=['POST'])
@login_required
def save_project_decision(project_id):
    """Save investment decision for a project"""
    project = ResearchProject.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.my_projects'))

    try:
        # Get form data
        decision = request.form.get('decision')  # invest, pass, watchlist
        decision_summary = request.form.get('decision_summary', '').strip()
        decision_confidence = request.form.get('decision_confidence', type=int)

        green_flags_raw = request.form.get('green_flags', '')
        red_flags_raw = request.form.get('red_flags', '')
        
        # Validate decision
        if decision not in ['invest', 'pass', 'watchlist']:
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

        # Different messages based on decision
        if decision == 'invest':
            flash(f'Decision recorded: Investing in {project.subject_display_name}! 🎯', 'success')
            # Redirect to portfolio if company exists
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
        flash(f'Error saving decision: {str(e)}', 'error')
        return redirect(url_for('research_workflow.project_summary', project_id=project_id))


@research_workflow_bp.route('/projects/<int:project_id>/add-finding', methods=['POST'])
@login_required
def add_finding(project_id):
    """Add a green or red flag finding to a project"""
    project = ResearchProject.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Access denied'}), 403

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
            return jsonify({'success': False, 'error': 'Finding text is required'}), 400

        if not finding_text:
            return jsonify({'success': False, 'error': 'Finding text is required'}), 400

        if finding_type == 'green':
            project.green_flags = (project.green_flags or []) + [finding_text]
        elif finding_type == 'red':
            project.red_flags = (project.red_flags or []) + [finding_text]
        else:
            return jsonify({'success': False, 'error': 'Invalid finding type'}), 400

        db.session.commit()
        
        # If it was a form submisison, redirect back. If AJAX, return JSON.
        if not request.is_json:
            flash(f'{finding_type.capitalize()} flag added!', 'success')
            return redirect(url_for('research_workflow.project_dashboard', project_id=project.id))
            
        return jsonify({'success': True, 'message': f'{finding_type.capitalize()} flag added'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@research_workflow_bp.route('/projects/<int:project_id>/remove-finding', methods=['POST'])
@login_required
def remove_finding(project_id):
    """Remove a finding from a project"""
    project = ResearchProject.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Access denied'}), 403

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
        return jsonify({'success': True, 'message': 'Finding removed'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@research_workflow_bp.route('/projects/<int:project_id>/update-thesis', methods=['POST'])
@login_required
def update_thesis(project_id):
    """Update the evolving investment thesis"""
    project = ResearchProject.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Access denied'}), 403

    try:
        data = request.get_json()
        thesis = data.get('thesis', '').strip()

        project.investment_thesis = thesis
        db.session.commit()

        return jsonify({'success': True, 'message': 'Thesis updated'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@research_workflow_bp.route('/projects/<int:project_id>/update-summary', methods=['POST'])
@login_required
def update_summary(project_id):
    """Update the project summary"""
    project = ResearchProject.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Access denied'}), 403

    try:
        data = request.get_json()
        summary = data.get('summary', '').strip()

        project.summary = summary
        db.session.commit()

        return jsonify({'success': True, 'message': 'Summary updated'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500