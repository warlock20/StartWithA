# StartWithA
# Copyright (C) 2024-2026 Kiran Mathews
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

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