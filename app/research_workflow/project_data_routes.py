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

        # Debug: Show what data we have in the project
        print(f"\n[DEBUG] Project ID: {project.id}")
        print(f"[DEBUG] Template steps: {len(project.template.workflow_steps) if project.template else 0}")
        print(f"[DEBUG] Step results keys: {list(project.step_results.keys()) if project.step_results else []}")
        print(f"[DEBUG] Step notes keys: {list(project.step_notes.keys()) if project.step_notes else []}")

        if project.step_results:
            for step_idx, step_data in project.step_results.items():
                print(f"[DEBUG] Step {step_idx} results type: {type(step_data)}")
                if isinstance(step_data, dict):
                    print(f"[DEBUG] Step {step_idx} keys: {list(step_data.keys())}")
                    if 'answers' in step_data:
                        answers = step_data.get('answers', {})
                        print(f"[DEBUG] Step {step_idx} has {len(answers)} answer entries")

        # Check what's in step_notes too
        if project.step_notes:
            for step_idx, note_data in project.step_notes.items():
                print(f"[DEBUG] Step {step_idx} notes type: {type(note_data)}")
                if isinstance(note_data, dict):
                    print(f"[DEBUG] Step {step_idx} notes keys: {list(note_data.keys())[:10]}")  # First 10 keys
                elif isinstance(note_data, str):
                    print(f"[DEBUG] Step {step_idx} notes length: {len(note_data)} chars")

        # Check template workflow steps structure
        if project.template and project.template.workflow_steps:
            for idx, step in enumerate(project.template.workflow_steps):
                if isinstance(step, dict):
                    print(f"[DEBUG] Template step {idx}: type={step.get('type')}, checklist_id={step.get('checklist_id')}")

        # Check for linked ChecklistAnalysis records
        analyses = ChecklistAnalysis.query.filter_by(
            user_id=project.user_id,
            company_id=project.company_id
        ).all()
        print(f"[DEBUG] Found {len(analyses)} ChecklistAnalysis records for this company")

        # Find the most recent completed ChecklistAnalysis
        checklist_analysis_id = None
        for analysis in analyses:
            answers = ChecklistAnswer.query.filter_by(checklist_analysis_id=analysis.id).all()
            answered_count = len([a for a in answers if a.answer_text and a.answer_text.strip()])
            print(f"[DEBUG]   - Analysis {analysis.id}: checklist_id={analysis.checklist_id}, status={analysis.status}, {answered_count} answers")

            # Use the first completed analysis (could be improved to find most recent)
            if analysis.status == 'completed' and not checklist_analysis_id:
                checklist_analysis_id = analysis.id
                print(f"[DEBUG] >>> Using ChecklistAnalysis {checklist_analysis_id} for quality score")

        # Calculate quality score with both project and checklist analysis
        quality_score = calculate_research_quality(
            research_project_id=project.id,
            research_session_id=checklist_analysis_id  # Pass the ChecklistAnalysis ID
        )
        print(f"[AI] ✓ Quality score calculated: {quality_score.overall_score if quality_score else 'None'}")
        print(f"[AI]   - Questions answered: {quality_score.questions_answered if quality_score else 0}")
        print(f"[AI]   - Questions total: {quality_score.questions_total if quality_score else 0}")
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

        # Validate decision
        if decision not in ['invest', 'pass', 'watchlist']:
            flash('Invalid decision type', 'error')
            return redirect(url_for('research_workflow.project_summary', project_id=project_id))

        # Update project
        project.decision = decision
        project.decision_summary = decision_summary
        project.decision_confidence = decision_confidence
        project.decision_date = now_utc()

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
        data = request.get_json()
        finding_type = data.get('type')  # 'green' or 'red'
        finding_text = data.get('text', '').strip()

        if not finding_text:
            return jsonify({'success': False, 'error': 'Finding text is required'}), 400

        if finding_type == 'green':
            if not project.green_flags:
                project.green_flags = []
            project.green_flags = project.green_flags + [finding_text]
        elif finding_type == 'red':
            if not project.red_flags:
                project.red_flags = []
            project.red_flags = project.red_flags + [finding_text]
        else:
            return jsonify({'success': False, 'error': 'Invalid finding type'}), 400

        db.session.commit()
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