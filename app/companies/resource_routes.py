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
Company Resource Routes
Unified JSON API for managing company files and links.
"""

import os
import uuid
import logging
from datetime import datetime

from flask import request, current_app, send_from_directory, abort, render_template
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app import db
from app.models import Company, CompanyResource
from app.companies import companies_bp
from app.utils.auth_utils import get_user_resource_or_403
from app.utils.response_utils import json_success, json_error, json_created, json_deleted, json_unauthorized

logger = logging.getLogger(__name__)

ALLOWED_RESOURCE_TYPES = {'pdf', 'txt', 'html'}


@companies_bp.route('/api/<int:company_id>/resources')
@login_required
def api_list_resources(company_id):
    """List company resources with optional filters."""
    company = get_user_resource_or_403(Company, company_id, current_user.id)

    query = CompanyResource.query.filter_by(company_id=company.id)

    resource_type = request.args.get('type')
    if resource_type in ('file', 'link'):
        query = query.filter_by(resource_type=resource_type)

    category = request.args.get('category')
    if category:
        query = query.filter_by(category=category)

    project_id = request.args.get('project_id', type=int)
    if project_id is not None:
        query = query.filter_by(research_project_id=project_id)

    step_index = request.args.get('step_index', type=int)
    if step_index is not None:
        query = query.filter_by(research_step_index=step_index)

    resources = query.order_by(CompanyResource.created_at.desc()).all()

    # Get distinct categories for filter dropdown
    categories = (
        db.session.query(CompanyResource.category)
        .filter(
            CompanyResource.company_id == company.id,
            CompanyResource.category.isnot(None),
        )
        .distinct()
        .all()
    )

    return json_success(data={
        'resources': [r.to_dict() for r in resources],
        'categories': [c[0] for c in categories if c[0]],
    })


@companies_bp.route('/api/<int:company_id>/resources/upload', methods=['POST'])
@login_required
def api_upload_resource(company_id):
    """Upload a file resource."""
    company = get_user_resource_or_403(Company, company_id, current_user.id)

    file = request.files.get('file')
    if not file or file.filename == '':
        return json_error('No file selected')

    title = request.form.get('title', '').strip()
    if not title:
        return json_error('Title is required')

    original_fn = secure_filename(file.filename)
    file_ext = os.path.splitext(original_fn)[1].lower().lstrip('.')

    if file_ext not in ALLOWED_RESOURCE_TYPES:
        return json_error(f'File type not allowed. Allowed: {", ".join(ALLOWED_RESOURCE_TYPES)}')

    try:
        stored_fn = f"{uuid.uuid4().hex}.{file_ext}"
        upload_dir = os.path.join(
            current_app.config['UPLOAD_FOLDER'], 'companies', str(company.id)
        )
        os.makedirs(upload_dir, exist_ok=True)
        file.save(os.path.join(upload_dir, stored_fn))

        # Parse optional resource_date
        resource_date = None
        date_str = request.form.get('resource_date', '').strip()
        if date_str:
            try:
                resource_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        resource = CompanyResource(
            company_id=company.id,
            user_id=current_user.id,
            resource_type='file',
            title=title,
            description=request.form.get('description', '').strip() or None,
            category=request.form.get('category', '').strip() or None,
            original_filename=original_fn,
            stored_filename=os.path.join('companies', str(company.id), stored_fn),
            file_type=file_ext,
            file_size=os.path.getsize(os.path.join(upload_dir, stored_fn)),
            research_project_id=request.form.get('project_id', type=int),
            research_step_index=request.form.get('step_index', type=int),
            resource_date=resource_date,
        )
        db.session.add(resource)
        db.session.commit()

        return json_created('File uploaded', data={'resource': resource.to_dict()})
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error uploading resource: {e}')
        return json_error(f'Upload failed: {str(e)}', status_code=500)


@companies_bp.route('/api/<int:company_id>/resources/link', methods=['POST'])
@login_required
def api_save_link(company_id):
    """Save a link resource."""
    company = get_user_resource_or_403(Company, company_id, current_user.id)

    data = request.get_json()
    if not data:
        return json_error('Invalid request body')

    title = (data.get('title') or '').strip()
    url = (data.get('url') or '').strip()
    if not title or not url:
        return json_error('Title and URL are required')

    try:
        resource = CompanyResource(
            company_id=company.id,
            user_id=current_user.id,
            resource_type='link',
            title=title,
            url=url,
            description=(data.get('description') or '').strip() or None,
            source_name=(data.get('source_name') or '').strip() or None,
            category=(data.get('category') or '').strip() or None,
            research_project_id=data.get('project_id'),
            research_step_index=data.get('step_index'),
        )
        db.session.add(resource)
        db.session.commit()

        return json_created('Link saved', data={'resource': resource.to_dict()})
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error saving link: {e}')
        return json_error(f'Failed to save link: {str(e)}', status_code=500)


@companies_bp.route('/api/resources/<int:resource_id>', methods=['DELETE'])
@login_required
def api_delete_resource(resource_id):
    """Delete a resource."""
    resource = CompanyResource.query.get_or_404(resource_id)

    if resource.company.user_id != current_user.id:
        return json_unauthorized()

    try:
        # Delete physical file if it's a file resource
        if resource.resource_type == 'file' and resource.stored_filename:
            file_path = os.path.join(
                current_app.config['UPLOAD_FOLDER'], resource.stored_filename
            )
            if os.path.exists(file_path):
                os.remove(file_path)

        db.session.delete(resource)
        db.session.commit()
        return json_deleted('Resource deleted', resource_id=resource_id)
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error deleting resource: {e}')
        return json_error(f'Failed to delete resource: {str(e)}', status_code=500)


@companies_bp.route('/api/resources/<int:resource_id>/download')
@login_required
def api_download_resource(resource_id):
    """Download a file resource."""
    resource = CompanyResource.query.get_or_404(resource_id)

    if resource.company.user_id != current_user.id:
        abort(403)

    if resource.resource_type != 'file':
        abort(400)

    file_path = os.path.join(
        current_app.config['UPLOAD_FOLDER'], resource.stored_filename
    )
    if not os.path.isfile(file_path):
        logger.error(f'Resource file not found on disk: {file_path}')
        abort(404)

    return send_from_directory(
        os.path.dirname(file_path),
        os.path.basename(file_path),
        as_attachment=True,
        download_name=resource.original_filename,
    )


@companies_bp.route('/api/resources/<int:resource_id>/view')
@login_required
def api_view_resource(resource_id):
    """Serve a file resource inline for in-app viewing."""
    resource = CompanyResource.query.get_or_404(resource_id)

    if resource.company.user_id != current_user.id:
        abort(403)

    if resource.resource_type != 'file':
        abort(400)

    file_path = os.path.join(
        current_app.config['UPLOAD_FOLDER'], resource.stored_filename
    )
    if not os.path.isfile(file_path):
        logger.error(f'Resource file not found on disk: {file_path}')
        abort(404)

    response = send_from_directory(
        os.path.dirname(file_path),
        os.path.basename(file_path),
        as_attachment=False,
    )
    response.headers['Content-Disposition'] = 'inline'
    return response


@companies_bp.route('/resources/<int:resource_id>/viewer')
@login_required
def resource_viewer(resource_id):
    """Full-page document viewer."""
    resource = CompanyResource.query.get_or_404(resource_id)

    if resource.company.user_id != current_user.id:
        abort(403)

    if resource.resource_type != 'file':
        abort(400)

    return render_template(
        'resource_viewer.html',
        resource=resource,
        company=resource.company,
        title=f'{resource.title} — Viewer',
    )
