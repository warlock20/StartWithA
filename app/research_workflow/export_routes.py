"""
Research Project Export
Export a full research project as a ZIP of markdown files + attachments.
"""

import logging
from flask import current_app, Response
from flask_login import current_user, login_required
from app.models import ResearchProject
from app.utils.auth_utils import get_user_resource_or_403
from app.research_workflow import research_workflow_bp
from app.services.export_service import export_research_project, safe_name
from app.research_workflow.pdf_report import generate_pdf_report
from app.utils.time_utils import now_utc

logger = logging.getLogger(__name__)


@research_workflow_bp.route('/projects/<int:project_id>/export')
@login_required
def export_project(project_id):
    """Export the entire research project as a ZIP archive"""
    project = get_user_resource_or_403(ResearchProject, project_id, current_user.id)

    company_name = safe_name(project.company.name if project.company else 'Unknown')
    date_str = now_utc().strftime('%Y-%m-%d')
    zip_filename = f"{company_name}_Research_{date_str}.zip"

    # Generate PDF report separately to keep export_service free of
    # circular imports with the research_workflow package
    pdf_bytes = None
    try:
        pdf_bytes = generate_pdf_report(project)
    except Exception:
        logger.warning("PDF report generation failed, skipping", exc_info=True)

    zip_bytes = export_research_project(
        project, current_app.config['UPLOAD_FOLDER'], pdf_bytes=pdf_bytes
    )

    return Response(
        zip_bytes,
        mimetype='application/zip',
        headers={'Content-Disposition': f'attachment; filename="{zip_filename}"'}
    )