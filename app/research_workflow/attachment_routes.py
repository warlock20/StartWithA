"""
Research Project Attachment Routes
Upload, download, and delete file attachments for research projects.
"""

import os
import uuid
from flask import (
    request, redirect, url_for, flash, current_app,
    send_from_directory, abort
)
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename
from app import db
from app.models import ResearchProject, ResearchAttachment
from app.research_workflow import research_workflow_bp
import logging

logger = logging.getLogger(__name__)

ALLOWED_ATTACHMENT_TYPES = {'pdf', 'txt'}


@research_workflow_bp.route('/projects/<int:project_id>/attachments', methods=['POST'])
@login_required
def upload_attachment(project_id):
    """Upload a file attachment to a research project"""
    project = ResearchProject.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.my_projects'))

    file = request.files.get('attachment_file')
    if not file or file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))

    title = request.form.get('attachment_title', '').strip()
    if not title:
        flash('Title is required', 'error')
        return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))

    step_index = request.form.get('step_index', type=int)  # None = project-level

    original_fn = secure_filename(file.filename)
    file_ext = os.path.splitext(original_fn)[1].lower().lstrip('.')

    if file_ext not in ALLOWED_ATTACHMENT_TYPES:
        flash(f'File type not allowed. Allowed: {", ".join(ALLOWED_ATTACHMENT_TYPES)}', 'error')
        return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))

    try:
        stored_fn = f"{uuid.uuid4().hex}.{file_ext}"
        upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'research', str(project_id))
        os.makedirs(upload_dir, exist_ok=True)
        file.save(os.path.join(upload_dir, stored_fn))

        attachment = ResearchAttachment(
            project_id=project_id,
            user_id=current_user.id,
            step_index=step_index,
            title=title,
            original_filename=original_fn,
            stored_filename=os.path.join('research', str(project_id), stored_fn),
            file_type=file_ext,
            file_size=os.path.getsize(os.path.join(upload_dir, stored_fn)),
        )
        db.session.add(attachment)
        db.session.commit()

        flash(f'Attached "{title}" successfully', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error uploading attachment: {e}')
        flash(f'Error uploading file: {e}', 'error')

    # Redirect back to step execution page if uploaded from there
    if step_index is not None:
        return redirect(url_for('research_workflow.execute_step', project_id=project_id, step_index=step_index))
    return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))


@research_workflow_bp.route('/projects/<int:project_id>/attachments/<int:attachment_id>/download')
@login_required
def download_attachment(project_id, attachment_id):
    """Download a research project attachment"""
    attachment = ResearchAttachment.query.get_or_404(attachment_id)

    if attachment.project.user_id != current_user.id or attachment.project_id != project_id:
        abort(403)

    return send_from_directory(
        current_app.config['UPLOAD_FOLDER'],
        attachment.stored_filename,
        as_attachment=True,
        download_name=attachment.original_filename
    )


@research_workflow_bp.route('/projects/<int:project_id>/attachments/<int:attachment_id>/delete', methods=['POST'])
@login_required
def delete_attachment(project_id, attachment_id):
    """Delete a research project attachment"""
    attachment = ResearchAttachment.query.get_or_404(attachment_id)

    if attachment.project.user_id != current_user.id or attachment.project_id != project_id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.my_projects'))

    try:
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], attachment.stored_filename)
        if os.path.exists(file_path):
            os.remove(file_path)

        db.session.delete(attachment)
        db.session.commit()
        flash('Attachment deleted', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error deleting attachment: {e}')
        flash(f'Error deleting attachment: {e}', 'error')

    return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))
