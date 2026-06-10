# Investment Checklist Platform
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
Document Annotation Routes
JSON API for CRUD operations on document annotations and dispatch to journal.
"""

import logging

from flask import request, url_for
from flask_login import current_user, login_required

from app import db
from app.models import Company, CompanyResource, JournalEntry, DocumentAnnotation
from app.companies import companies_bp
from app.utils.response_utils import (
    json_success, json_error, json_created, json_deleted, json_updated, json_unauthorized,
)

logger = logging.getLogger(__name__)

VALID_SCOPES = {'company', 'sector', 'general'}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_resource_or_403(resource_id):
    """Return a CompanyResource owned by the current user, or abort 403."""
    resource = CompanyResource.query.get_or_404(resource_id)
    if resource.company.user_id != current_user.id:
        return None, json_unauthorized()
    return resource, None


def _get_annotation_or_403(annotation_id):
    """Return a DocumentAnnotation owned by the current user, or abort 403."""
    annotation = DocumentAnnotation.query.get_or_404(annotation_id)
    if annotation.user_id != current_user.id:
        return None, json_unauthorized()
    return annotation, None


# ---------------------------------------------------------------------------
# List annotations for a resource
# ---------------------------------------------------------------------------

@companies_bp.route('/api/resources/<int:resource_id>/annotations')
@login_required
def api_list_annotations(resource_id):
    """List all annotations for a given document resource."""
    resource, err = _get_resource_or_403(resource_id)
    if err:
        return err

    annotations = (
        DocumentAnnotation.query
        .filter_by(resource_id=resource_id, user_id=current_user.id)
        .order_by(DocumentAnnotation.page_number, DocumentAnnotation.created_at)
        .all()
    )

    return json_success(data={
        'annotations': [a.to_dict() for a in annotations],
    })


# ---------------------------------------------------------------------------
# List all annotations for a company (across all documents)
# ---------------------------------------------------------------------------

@companies_bp.route('/api/<int:company_id>/annotations')
@login_required
def api_list_company_annotations(company_id):
    """List all annotations across all documents for a company."""
    company = Company.query.get_or_404(company_id)
    if company.user_id != current_user.id:
        return json_unauthorized()

    annotations = (
        DocumentAnnotation.query
        .filter_by(company_id=company_id, user_id=current_user.id)
        .order_by(DocumentAnnotation.created_at.desc())
        .all()
    )

    # Fetch resource titles for display
    resource_ids = set(a.resource_id for a in annotations)
    resources = {}
    if resource_ids:
        resources = {
            r.id: r for r in
            CompanyResource.query.filter(CompanyResource.id.in_(resource_ids)).all()
        }

    result = []
    for a in annotations:
        d = a.to_dict()
        res = resources.get(a.resource_id)
        d['resource_title'] = res.title if res else 'Unknown Document'
        result.append(d)

    return json_success(data={'annotations': result})


# ---------------------------------------------------------------------------
# Create annotation
# ---------------------------------------------------------------------------

@companies_bp.route('/api/resources/<int:resource_id>/annotations', methods=['POST'])
@login_required
def api_create_annotation(resource_id):
    """Create a point-pin or text-highlight annotation on a document page."""
    resource, err = _get_resource_or_403(resource_id)
    if err:
        return err

    data = request.get_json()
    if not data:
        return json_error('Request body must be JSON', status_code=400)

    annotation_type = data.get('annotation_type', 'pin')
    if annotation_type not in ('pin', 'highlight'):
        return json_error('annotation_type must be pin or highlight', status_code=400)

    page_number = data.get('page_number')
    content = (data.get('content') or '').strip()
    scope = data.get('scope', 'company')

    if page_number is None or not isinstance(page_number, int) or page_number < 1:
        return json_error('page_number must be a positive integer', status_code=400)
    if not content:
        return json_error('content is required', status_code=400)
    if scope not in VALID_SCOPES:
        return json_error(f'scope must be one of: {", ".join(VALID_SCOPES)}', status_code=400)

    x_percent = None
    y_percent = None
    anchor_text = None

    if annotation_type == 'pin':
        x_percent = data.get('x_percent')
        y_percent = data.get('y_percent')
        if x_percent is None or not isinstance(x_percent, (int, float)):
            return json_error('x_percent is required for pin annotations', status_code=400)
        if y_percent is None or not isinstance(y_percent, (int, float)):
            return json_error('y_percent is required for pin annotations', status_code=400)
        x_percent = max(0.0, min(100.0, float(x_percent)))
        y_percent = max(0.0, min(100.0, float(y_percent)))
    else:
        anchor_text = (data.get('anchor_text') or '').strip()
        if not anchor_text:
            return json_error('anchor_text is required for highlight annotations', status_code=400)

    annotation = DocumentAnnotation(
        resource_id=resource_id,
        company_id=resource.company_id,
        user_id=current_user.id,
        annotation_type=annotation_type,
        page_number=page_number,
        x_percent=x_percent,
        y_percent=y_percent,
        anchor_text=anchor_text,
        content=content,
        scope=scope,
    )
    db.session.add(annotation)
    db.session.commit()

    return json_created('Annotation created', data={'annotation': annotation.to_dict()})


# ---------------------------------------------------------------------------
# Update annotation
# ---------------------------------------------------------------------------

@companies_bp.route('/api/annotations/<int:annotation_id>', methods=['PUT'])
@login_required
def api_update_annotation(annotation_id):
    """Update the content or scope of an annotation."""
    annotation, err = _get_annotation_or_403(annotation_id)
    if err:
        return err

    data = request.get_json()
    if not data:
        return json_error('Request body must be JSON', status_code=400)

    if 'content' in data:
        content = (data['content'] or '').strip()
        if not content:
            return json_error('content cannot be empty', status_code=400)
        annotation.content = content

    if 'scope' in data:
        scope = data['scope']
        if scope not in VALID_SCOPES:
            return json_error(f'scope must be one of: {", ".join(VALID_SCOPES)}', status_code=400)
        annotation.scope = scope

    db.session.commit()

    return json_updated('Annotation updated', data={'annotation': annotation.to_dict()})


# ---------------------------------------------------------------------------
# Delete annotation
# ---------------------------------------------------------------------------

@companies_bp.route('/api/annotations/<int:annotation_id>', methods=['DELETE'])
@login_required
def api_delete_annotation(annotation_id):
    """Delete an annotation."""
    annotation, err = _get_annotation_or_403(annotation_id)
    if err:
        return err

    db.session.delete(annotation)
    db.session.commit()

    return json_deleted('Annotation deleted', resource_id=annotation_id)


# ---------------------------------------------------------------------------
# Send annotation to journal
# ---------------------------------------------------------------------------

@companies_bp.route('/api/annotations/<int:annotation_id>/send-to-journal', methods=['POST'])
@login_required
def api_send_annotation_to_journal(annotation_id):
    """Create a JournalEntry from an annotation."""
    annotation, err = _get_annotation_or_403(annotation_id)
    if err:
        return err

    resource = CompanyResource.query.get(annotation.resource_id)

    entry = JournalEntry(
        user_id=current_user.id,
        title=f'Note from {resource.title} (p. {annotation.page_number})',
        entry_type='observation',
        content=annotation.content,
        company_id=annotation.company_id,
        source='document_annotation',
        source_url=url_for(
            'companies.resource_viewer',
            resource_id=resource.id,
            _external=True,
        ),
        tags=['document-note'],
    )
    db.session.add(entry)
    db.session.commit()

    return json_created('Sent to journal', data={
        'journal_entry_id': entry.id,
    })
