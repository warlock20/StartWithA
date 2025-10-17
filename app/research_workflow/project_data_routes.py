"""
Project Data Routes Module

This module handles all routes related to project content and data including:
- Viewing project notes and summaries
- Saving project decisions
- Adding findings (green/red flags)
- Updating investment thesis

Extracted from routes.py lines: 189-226, 228-251, 253-303, 314-334, 337-370
"""

from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user, login_required
from app import db
from app.models import ResearchTemplate, ResearchProject
from app.research_workflow import research_workflow_bp
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
                          title=f"Research Notes - {project.research_subject_name}",
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

    return render_template('project_summary.html',
                          title=f"Summary: {project.project_name}",
                          project=project,
                          all_notes=all_notes)


@research_workflow_bp.route('/projects/<int:project_id>/decision', methods=['POST'])
@login_required
def save_decision(project_id):
    """Save final investment decision for a project"""
    project = ResearchProject.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.my_projects'))

    # --- Get form data ---
    decision = request.form.get('decision')
    project.decision = decision  # Save the decision to the project
    project.decision_confidence = request.form.get('confidence', type=int)
    project.decision_notes = request.form.get('decision_notes')
    project.decision_date = now_utc()

    # Parse key findings
    green_flags = request.form.get('green_flags', '').split('\n')
    red_flags = request.form.get('red_flags', '').split('\n')
    project.green_flags = [f.strip() for f in green_flags if f.strip()]
    project.red_flags = [f.strip() for f in red_flags if f.strip()]

    # Update template success metrics
    if project.decision == 'invest':
        project.template.successful_investments += 1
    elif project.decision == 'pass':
        project.template.failed_investments += 1

    # --- Add company to watchlist if decision is watchlist ---
    flash_message = 'Decision saved!'  # Default message

    if decision == 'watchlist' and project.company:
        company_to_watch = project.company
        if company_to_watch not in current_user.favorites:
            current_user.favorites.append(company_to_watch)
            flash_message = f'Decision saved. "{company_to_watch.name}" has been added to your Favorites/Watchlist.'

    try:
        db.session.commit()
        flash(flash_message, 'success')  # Use the dynamic flash message

        if project.decision == 'invest':
            # Redirect to portfolio or next steps
            return redirect(url_for('companies.companies_dashboard'))
        else:
            # Back to project list
            return redirect(url_for('research_workflow.my_projects'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error saving decision: {str(e)}', 'error')
        return redirect(request.referrer)


@research_workflow_bp.route('/projects/<int:project_id>/update-thesis', methods=['POST'])
@login_required
def update_thesis(project_id):
    """Update the investment thesis for a research project"""
    project = ResearchProject.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.my_projects'))

    thesis = request.form.get('investment_thesis', '').strip()
    project.investment_thesis = thesis
    project.last_worked_at = now_utc()

    try:
        db.session.commit()
        flash('Investment thesis updated', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating thesis: {str(e)}', 'error')

    return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))


@research_workflow_bp.route('/projects/<int:project_id>/add-finding', methods=['POST'])
@login_required
def add_finding(project_id):
    """Add a key finding to a research project"""
    project = ResearchProject.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403

    finding_type = request.form.get('finding_type')  # 'green_flag' or 'red_flag'
    finding_text = request.form.get('finding_text', '').strip()

    if not finding_text:
        return jsonify({'error': 'Finding text is required'}), 400

    if finding_type == 'green_flag':
        if not project.green_flags:
            project.green_flags = []
        project.green_flags = project.green_flags + [finding_text]
    elif finding_type == 'red_flag':
        if not project.red_flags:
            project.red_flags = []
        project.red_flags = project.red_flags + [finding_text]
    else:
        return jsonify({'error': 'Invalid finding type'}), 400

    project.last_worked_at = now_utc()

    try:
        db.session.commit()
        return jsonify({'success': True, 'message': 'Finding added'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
