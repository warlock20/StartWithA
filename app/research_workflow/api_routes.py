"""
API Routes Module for Research Workflow

This module contains all REST API endpoints for AJAX requests in the research workflow.
"""

from flask import jsonify, request
from flask_login import current_user, login_required
from app.models import (ResearchTemplate, ResearchProject, Company, BackgroundTask)
from app.research_workflow import research_workflow_bp
from app.services.background_tasks import BackgroundTaskService
from app.services.adaptive_template_service import (
    suggest_template_adaptations,
    apply_template_adaptations,
    adaptive_template_service
)
from app.utils.time_utils import now_utc
import logging

logger = logging.getLogger(__name__)


@research_workflow_bp.route('/api/server-time')
@login_required
def get_server_time():
    """API endpoint to get current server time for timer synchronization"""
    return jsonify({
        'server_time': now_utc().isoformat(),
        'timezone': 'UTC'
    })


@research_workflow_bp.route('/api/template/<int:template_id>/adaptations')
@login_required
def get_template_adaptations(template_id):
    """Get adaptive suggestions for a research template based on company context"""
    template = ResearchTemplate.query.get_or_404(template_id)

    # Security check
    if template.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403

    # Get company from request parameters
    company_id = request.args.get('company_id', type=int)
    if not company_id:
        return jsonify({'error': 'Company ID required'}), 400

    company = Company.query.get_or_404(company_id)
    if company.user_id != current_user.id:
        return jsonify({'error': 'Access denied to company'}), 403

    try:
        logger.info(f"Getting adaptations for template {template_id}, company {company_id}")

        # Get comprehensive adaptations
        adaptations = suggest_template_adaptations(template, company, current_user.id)

        logger.info(f"Successfully generated adaptations: {adaptations}")

        return jsonify({
            'success': True,
            'adaptations': adaptations,
            'template_id': template_id,
            'company_id': company_id
        })

    except Exception as e:
        logger.error(f"Error getting template adaptations: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__
        }), 500


@research_workflow_bp.route('/api/template/<int:template_id>/apply-adaptations', methods=['POST'])
@login_required
def apply_adaptations(template_id):
    """Apply selected adaptations to a research template"""
    template = ResearchTemplate.query.get_or_404(template_id)

    # Security check
    if template.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403

    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No adaptation data provided'}), 400

        # Apply the adaptations
        success = apply_template_adaptations(template, data)

        if success:
            return jsonify({
                'success': True,
                'message': 'Template adaptations applied successfully',
                'template_id': template_id
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to apply adaptations'
            }), 500

    except Exception as e:
        logger.error(f"Error applying template adaptations: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@research_workflow_bp.route('/api/template/<int:template_id>/time-estimates')
@login_required
def get_personalized_time_estimates(template_id):
    """Get personalized time estimates for template steps based on user history"""
    template = ResearchTemplate.query.get_or_404(template_id)

    # Security check
    if template.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403

    try:
        estimates = adaptive_template_service.get_personalized_time_estimates(
            template, current_user.id
        )

        return jsonify({
            'success': True,
            'estimates': estimates,
            'template_id': template_id
        })

    except Exception as e:
        logger.error(f"Error getting time estimates: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@research_workflow_bp.route('/api/company/<int:company_id>/sector-questions')
@login_required
def get_sector_questions(company_id):
    """Get sector-specific questions available for a company"""
    company = Company.query.get_or_404(company_id)

    # Security check
    if company.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403

    try:
        if not company.sector:
            return jsonify({
                'success': True,
                'questions': [],
                'message': 'No sector specified for this company'
            })

        questions = adaptive_template_service.get_sector_questions(
            company.sector, current_user.id
        )

        return jsonify({
            'success': True,
            'questions': questions,
            'sector': company.sector,
            'company_id': company_id
        })

    except Exception as e:
        logger.error(f"Error getting sector questions: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@research_workflow_bp.route('/api/project/<int:project_id>/adaptive-suggestions')
@login_required
def get_project_adaptive_suggestions(project_id):
    """Get adaptive suggestions when starting a new research project"""
    project = ResearchProject.query.get_or_404(project_id)

    # Security check
    if project.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403

    try:
        template = project.template
        company = project.company

        logger.info(f"Getting project suggestions for project {project_id}, template: {template.id if template else 'None'}, company: {company.id if company else 'None'}")

        if not company:
            logger.warning(f"Project {project_id} has no company associated")
            return jsonify({
                'success': True,
                'suggestions': [],
                'message': 'No company associated with this project'
            })

        if not company.sector:
            logger.warning(f"Company {company.id} has no sector specified")
            return jsonify({
                'success': True,
                'suggestions': [],
                'message': f'No sector specified for {company.name}'
            })

        # Get comprehensive suggestions
        adaptations = suggest_template_adaptations(template, company, current_user.id)

        # Calculate potential time savings/additions
        step_suggestions = adaptations.get('step_injections', {}).get('suggestions', [])
        time_estimates = adaptations.get('time_estimates', {}).get('estimates', [])

        # Create actionable suggestions summary
        suggestions_summary = {
            'sector_questions_available': len(step_suggestions),
            'time_estimates_available': len([e for e in time_estimates if e.get('confidence', 0) > 0.5]),
            'recommended_injections': [
                {
                    'step_name': s['step_name'],
                    'questions_count': len(s['questions']),
                    'confidence': s['confidence']
                }
                for s in step_suggestions
                if s['confidence'] > 0.7
            ],
            'time_insights': adaptations.get('time_estimates', {}).get('insights', [])
        }

        return jsonify({
            'success': True,
            'suggestions': suggestions_summary,
            'full_adaptations': adaptations,
            'project_id': project_id
        })

    except Exception as e:
        logger.error(f"Error getting project adaptive suggestions: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__
        }), 500


@research_workflow_bp.route('/api/background-task/<string:task_id>', methods=['GET'])
@login_required
def get_background_task_status(task_id):
    """Get status of a background task"""
    try:
        status = BackgroundTaskService.get_task_status(task_id)
        if not status:
            return jsonify({'success': False, 'error': 'Task not found'}), 404

        # Check if task belongs to current user
        task = BackgroundTask.query.get(task_id)
        if task and task.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        return jsonify({
            'success': True,
            'status': status
        })

    except Exception as e:
        logger.error(f"Error getting task status: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error getting task status: {str(e)}'
        }), 500


@research_workflow_bp.route('/api/running-tasks', methods=['GET'])
@login_required
def get_running_tasks():
    """Check for running background tasks for a specific project/step"""
    try:
        project_id = request.args.get('project_id', type=int)
        step_index = request.args.get('step_index', type=int)

        if not project_id or step_index is None:
            return jsonify({'success': False, 'error': 'Missing parameters'}), 400

        # Find running task for this project/step
        running_task = BackgroundTask.query.filter_by(
            user_id=current_user.id,
            project_id=project_id,
            step_index=step_index,
            task_type='competitor_analysis'
        ).filter(
            BackgroundTask.status.in_(['pending', 'running'])
        ).first()

        if running_task:
            return jsonify({
                'success': True,
                'task_id': running_task.id,
                'status': running_task.status
            })
        else:
            return jsonify({
                'success': True,
                'task_id': None
            })

    except Exception as e:
        logger.error(f"Error checking running tasks: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error checking running tasks: {str(e)}'
        }), 500
