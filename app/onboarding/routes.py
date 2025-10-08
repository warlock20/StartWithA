"""
Onboarding System Routes
Handles the "Guided First Ten Minutes" onboarding experience
"""

from flask import jsonify, request, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime, timezone
from app.utils.time_utils import now_utc
import logging

from app.onboarding import onboarding_bp
from app import db
from app.models import (
    User, OnboardingProgress, Company, KillChecklist, KillCriterion,
    ResearchTemplate, ResearchProject, Checklist, ChecklistItem
)

logger = logging.getLogger(__name__)


@onboarding_bp.route('/welcome')
@login_required
def welcome():
    """Show onboarding welcome page"""
    # If user has already completed onboarding, redirect to dashboard
    if current_user.onboarding_completed:
        return redirect(url_for('analytics.dashboard'))

    return render_template('onboarding/welcome.html')


@onboarding_bp.route('/start', methods=['GET', 'POST'])
@login_required
def start_onboarding():
    """Initialize onboarding process for new users"""

    # Check if user has already completed onboarding
    if current_user.onboarding_completed:
        flash('You have already completed the onboarding process!', 'info')
        return redirect(url_for('analytics.dashboard'))

    if request.method == 'GET':
        # Show onboarding welcome page
        return render_template('onboarding/welcome.html')

    # POST: Start the onboarding process
    try:
        # Initialize or get existing onboarding progress
        progress = OnboardingProgress.query.filter_by(user_id=current_user.id).first()
        if not progress:
            progress = OnboardingProgress(
                user_id=current_user.id,
                current_step=0,
                step_start_times={},
                step_completion_times={},
                completed_steps=[]
            )
            db.session.add(progress)

        # Update user onboarding status
        current_user.onboarding_started_at = now_utc()
        current_user.onboarding_step = 1

        # Start timing for step 1
        progress.current_step = 1
        progress.step_start_times['1'] = now_utc().isoformat()

        db.session.commit()

        logger.info(f"User {current_user.id} started onboarding")

        return jsonify({
            'success': True,
            'message': 'Onboarding started successfully',
            'next_step': 1,
            'redirect_url': url_for('onboarding.step', step_number=1)
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error starting onboarding for user {current_user.id}: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to start onboarding process'
        }), 500


@onboarding_bp.route('/step/<int:step_number>')
@login_required
def step(step_number):
    """Display specific onboarding step"""

    # Validate step number
    if step_number < 1 or step_number > 6:
        flash('Invalid onboarding step', 'error')
        return redirect(url_for('onboarding.start_onboarding'))

    # Check if user should be on this step
    if not current_user.onboarding_started_at:
        return redirect(url_for('onboarding.start_onboarding'))

    if current_user.onboarding_completed:
        return redirect(url_for('analytics.dashboard'))

    # Get onboarding progress
    progress = OnboardingProgress.query.filter_by(user_id=current_user.id).first()
    if not progress:
        return redirect(url_for('onboarding.start_onboarding'))

    # Render appropriate template for step
    templates = {
        1: 'onboarding/step1_philosophy.html',
        2: 'onboarding/step2_company_capture.html',
        3: 'onboarding/step3_kill_checklist.html',
        4: 'onboarding/step4_research_template.html',
        5: 'onboarding/step5_checklist_creation.html',
        6: 'onboarding/step6_quick_research.html'
    }

    template = templates.get(step_number, 'onboarding/step1_philosophy.html')

    return render_template(template,
                         step_number=step_number,
                         progress=progress,
                         total_steps=5)


@onboarding_bp.route('/api/step/<int:step_number>/complete', methods=['POST'])
@login_required
def complete_step(step_number):
    """Mark an onboarding step as complete and save data"""

    try:
        data = request.get_json()

        # Get onboarding progress
        progress = OnboardingProgress.query.filter_by(user_id=current_user.id).first()
        if not progress:
            return jsonify({'success': False, 'error': 'Onboarding not started'}), 400

        # Complete the step
        completion_time = now_utc()

        # Update progress tracking
        progress.step_completion_times[str(step_number)] = completion_time.isoformat()

        # Add to completed steps if not already there
        if step_number not in progress.completed_steps:
            progress.completed_steps.append(step_number)

        # Handle step-specific data
        if step_number == 2:
            # Step 2: Company capture
            company_id = data.get('company_id')
            company_reason = data.get('company_reason', '').strip()

            if company_id:
                # Use existing company from company search
                company = Company.query.get(company_id)
                if company:
                    progress.first_company_name = company.name
                    progress.first_company_id = company.id

                    # Update company with user's reason if provided
                    if company_reason:
                        if company.summary:
                            company.summary += f"\n\nOnboarding reason: {company_reason}"
                        else:
                            company.summary = f"Onboarding reason: {company_reason}"

                    logger.info(f"Selected existing company '{company.name}' (ID: {company.id}) for user {current_user.id}")
                else:
                    return jsonify({'success': False, 'error': 'Selected company not found'}), 400
            else:
                return jsonify({'success': False, 'error': 'No company selected'}), 400

        elif step_number == 3:
            # Step 3: Kill checklist results
            kill_results = data.get('kill_results', {})
            company_survived = data.get('company_survived', False)

            # Create a basic kill checklist for the user
            kill_checklist = KillChecklist(
                name="My First Kill Checklist",
                description="Basic kill checklist created during onboarding",
                user_id=current_user.id
            )
            db.session.add(kill_checklist)
            db.session.flush()

            # Add the basic kill criteria
            basic_criteria = [
                "Do I understand how this company makes money?",
                "Is the balance sheet healthy? (Low debt)",
                "Would I be comfortable holding this for 5 years?"
            ]

            for i, criterion_text in enumerate(basic_criteria):
                criterion = KillCriterion(
                    kill_checklist_id=kill_checklist.id,
                    question=criterion_text,
                    order=i + 1,
                    times_evaluated=1,
                    times_failed=1 if not company_survived else 0
                )
                db.session.add(criterion)

            progress.first_kill_checklist_id = kill_checklist.id

        elif step_number == 4:
            # Step 4: Research template creation - Simplified 3-step template
            if data.get('create_template', False):
                # First, create a proper checklist in the database
                checklist = Checklist(
                    name="My Simple Checklist",
                    description="Basic investment evaluation checklist created during onboarding",
                    user_id=current_user.id
                )
                db.session.add(checklist)
                db.session.flush()  # Get the checklist ID

                # Add the checklist items
                checklist_questions = [
                    "How does this company make money and is their business model sustainable?",
                    "What are the main financial health indicators and do they look strong?",
                    "Is this stock reasonably priced compared to its growth prospects?"
                ]

                for i, question in enumerate(checklist_questions):
                    item = ChecklistItem(
                        text=question,
                        checklist_id=checklist.id,
                        order=i + 1,
                        llm_prompt=""
                    )
                    db.session.add(item)

                # Create simplified 3-step research template
                template = ResearchTemplate(
                    name="My First Research Template",
                    description="Simplified research template created during onboarding",
                    user_id=current_user.id,
                    workflow_steps=[
                        {
                            "name": "Analyze and Understand the Business Model",
                            "description": "Research how the company makes money and if the business model is sustainable",
                            "type": "business_model_analysis",
                            "estimated_minutes": 30,
                            "order": 1
                        },
                        {
                            "name": "My Simple Checklist",
                            "description": "Answer focused questions to evaluate this investment opportunity",
                            "type": "checklist",
                            "estimated_minutes": 20,
                            "order": 2,
                            "config": {
                                "checklist_id": checklist.id
                            }
                        },
                        {
                            "name": "My Investment Thesis",
                            "description": "Write a clear, concise thesis summarizing your investment decision",
                            "type": "thesis_writing",
                            "estimated_minutes": 30,
                            "order": 3,
                            "config": {
                                "thesis_template": "simplified_onboarding",
                                "sections": [
                                    "Investment Summary",
                                    "Key Reasons to Invest",
                                    "Major Risks",
                                    "Expected Outcome"
                                ]
                            }
                        }
                    ]
                )
                db.session.add(template)
                db.session.flush()

                progress.first_research_template_id = template.id

                # If company survived kill checklist, create a research project
                if progress.first_company_id:
                    research_project = ResearchProject(
                        user_id=current_user.id,
                        template_id=template.id,
                        company_id=progress.first_company_id,
                        project_name=f"Research: {progress.first_company_name}",
                        status='active'
                    )
                    db.session.add(research_project)
                    db.session.flush()

                    # Store the research project ID for Step 5 integration
                    progress.first_research_project_id = research_project.id

        elif step_number == 5:
            # Step 5: Final step - Complete onboarding and redirect to research
            time_spent = data.get('time_spent', 0)

            # Mark onboarding as completed
            current_user.onboarding_completed = True
            current_user.onboarding_completed_at = completion_time
            current_user.onboarding_step = 5
            progress.completed_at = completion_time
            progress.checklist_confirmed = True
            progress.checklist_confirmation_time = completion_time

        elif step_number == 6:
            # Step 6: Complete onboarding (thesis step is already in template)
            current_user.onboarding_completed = True
            current_user.onboarding_completed_at = completion_time
            current_user.onboarding_step = 6
            progress.completed_at = completion_time

            # Collect feedback
            feedback = data.get('feedback', '')
            satisfaction = data.get('satisfaction_score', None)

            if feedback:
                progress.onboarding_feedback = feedback
            if satisfaction:
                progress.satisfaction_score = satisfaction

        # Move to next step (unless this is the last step)
        if step_number < 6:
            next_step = step_number + 1
            progress.current_step = next_step
            current_user.onboarding_step = next_step

            # Start timing for next step
            progress.step_start_times[str(next_step)] = completion_time.isoformat()

        db.session.commit()

        response_data = {
            'success': True,
            'message': f'Step {step_number} completed successfully',
            'completed_step': step_number,
            'total_steps': 5
        }

        if step_number < 5:
            response_data['next_step'] = step_number + 1
            response_data['redirect_url'] = url_for('onboarding.step', step_number=step_number + 1)
        elif step_number == 5:
            response_data['onboarding_complete'] = True
            response_data['message'] = "Let's start your research!"
            # Redirect to the research project created in step 4
            if progress.first_research_project_id:
                response_data['redirect_url'] = url_for('research_workflow.project_dashboard', project_id=progress.first_research_project_id, from_onboarding='true')
            else:
                response_data['redirect_url'] = url_for('analytics.dashboard')
        else:
            response_data['onboarding_complete'] = True
            response_data['redirect_url'] = url_for('analytics.dashboard')

        return jsonify(response_data)

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error completing step {step_number} for user {current_user.id}: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to complete step {step_number}'
        }), 500


@onboarding_bp.route('/api/progress')
@login_required
def get_progress():
    """Get current onboarding progress for user"""

    progress = OnboardingProgress.query.filter_by(user_id=current_user.id).first()

    if not progress:
        return jsonify({
            'onboarding_started': False,
            'onboarding_completed': current_user.onboarding_completed,
            'current_step': 0,
            'completed_steps': []
        })

    return jsonify({
        'onboarding_started': True,
        'onboarding_completed': current_user.onboarding_completed,
        'current_step': progress.current_step,
        'completed_steps': progress.completed_steps,
        'first_company_name': progress.first_company_name,
        'created_at': progress.created_at.isoformat() if progress.created_at else None,
        'completed_at': progress.completed_at.isoformat() if progress.completed_at else None
    })


@onboarding_bp.route('/skip', methods=['POST'])
@login_required
def skip_onboarding():
    """Allow users to skip onboarding (not recommended)"""

    try:
        current_user.onboarding_completed = True
        current_user.onboarding_completed_at = now_utc()
        current_user.onboarding_step = 5

        # Create minimal onboarding progress record
        progress = OnboardingProgress.query.filter_by(user_id=current_user.id).first()
        if not progress:
            progress = OnboardingProgress(
                user_id=current_user.id,
                current_step=5,
                completed_steps=[],
                completed_at=now_utc()
            )
            db.session.add(progress)
        else:
            progress.completed_at = now_utc()

        db.session.commit()

        logger.info(f"User {current_user.id} skipped onboarding")

        return jsonify({
            'success': True,
            'message': 'Onboarding skipped successfully',
            'redirect_url': url_for('analytics.dashboard')
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error skipping onboarding for user {current_user.id}: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to skip onboarding'
        }), 500


@onboarding_bp.route('/admin/reset', methods=['POST'])
@login_required
def admin_reset_onboarding():
    """
    ADMIN ONLY: Reset onboarding state for testing purposes
    This allows testing the onboarding flow multiple times
    """

    try:
        # Reset user onboarding fields
        current_user.onboarding_completed = False
        current_user.onboarding_completed_at = None
        current_user.onboarding_started_at = None
        current_user.onboarding_step = 0

        # Delete existing onboarding progress
        progress = OnboardingProgress.query.filter_by(user_id=current_user.id).first()
        if progress:
            db.session.delete(progress)

        # Optionally clean up test data created during onboarding
        # (You can enable these if you want to clean up test companies/templates)
        # Note: Be careful with this in production!

        # Delete companies created during onboarding tests
        # test_companies = Company.query.filter_by(user_id=current_user.id).all()
        # for company in test_companies:
        #     db.session.delete(company)

        # Delete kill checklists created during onboarding
        # test_checklists = KillChecklist.query.filter_by(user_id=current_user.id).all()
        # for checklist in test_checklists:
        #     db.session.delete(checklist)

        # Delete research templates created during onboarding
        # test_templates = ResearchTemplate.query.filter_by(user_id=current_user.id).all()
        # for template in test_templates:
        #     db.session.delete(template)

        db.session.commit()

        logger.info(f"ADMIN: Reset onboarding state for user {current_user.id}")

        return jsonify({
            'success': True,
            'message': 'Onboarding state reset successfully! You can now test the onboarding flow again.',
            'redirect_url': url_for('onboarding.welcome')
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error resetting onboarding for user {current_user.id}: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to reset onboarding state'
        }), 500


@onboarding_bp.route('/admin/reset-page')
@login_required
def admin_reset_page():
    """Show admin page for resetting onboarding"""
    return render_template('onboarding/admin_reset.html')


@onboarding_bp.route('/test-reset')
@login_required
def quick_reset():
    """Quick onboarding reset for testing"""
    try:
        # Reset user onboarding fields
        current_user.onboarding_completed = False
        current_user.onboarding_completed_at = None
        current_user.onboarding_started_at = None
        current_user.onboarding_step = 0

        # Delete existing onboarding progress
        progress = OnboardingProgress.query.filter_by(user_id=current_user.id).first()
        if progress:
            db.session.delete(progress)

        db.session.commit()
        flash('Onboarding reset successfully! You can test the flow again.', 'success')
        return redirect(url_for('onboarding.welcome'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error resetting onboarding: {str(e)}', 'error')
        return redirect(url_for('analytics.dashboard'))


@onboarding_bp.route('/test-reset-simple')
@login_required
def quick_reset_simple():
    """Even simpler onboarding reset - goes directly to step 1"""
    try:
        # Reset user onboarding fields
        current_user.onboarding_completed = False
        current_user.onboarding_completed_at = None
        current_user.onboarding_started_at = None
        current_user.onboarding_step = 0

        # Delete existing onboarding progress
        progress = OnboardingProgress.query.filter_by(user_id=current_user.id).first()
        if progress:
            db.session.delete(progress)

        db.session.commit()
        flash('Onboarding reset! Starting step 1...', 'success')
        return redirect(url_for('onboarding.step', step_number=1))
    except Exception as e:
        db.session.rollback()
        flash(f'Error resetting onboarding: {str(e)}', 'error')
        return redirect(url_for('analytics.dashboard'))