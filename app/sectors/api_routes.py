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

# app/sectors/api_routes.py

from flask import jsonify, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func
from app import db
from app.models import Sector, SectorAnalysis, SectorSection, SectorNote, Company
from app.services.sector_service import SectorService
from app.sectors import sectors_bp
from app.sectors.routes import initialize_default_sections
from app.utils.response_utils import json_error, json_unauthorized


@sectors_bp.route('/api/sectors/autocomplete', methods=['GET'])
@login_required
def autocomplete_sectors():
    """
    Autocomplete endpoint for sector selection.

    Query params:
        q: Search query string
        limit: Maximum results (default 10)

    Returns:
        JSON array of sector objects
    """
    query = request.args.get('q', '').strip()
    limit = request.args.get('limit', 10, type=int)

    # Limit max results to prevent abuse
    limit = min(limit, 50)

    sectors = SectorService.get_sector_autocomplete(current_user.id, query, limit)

    return jsonify([{
        'id': s.id,
        'name': s.name,
        'display_name': s.display_name,
        'slug': s.slug,
        'icon': s.icon,
        'color': s.color,
        'total_companies': s.total_companies,
        'companies_analyzed': s.companies_analyzed,
        'competence_level': s.competence_level
    } for s in sectors])


@sectors_bp.route('/api/sectors', methods=['GET'])
@login_required
def list_sectors():
    """
    List all sectors for current user.

    Query params:
        include_inactive: Include archived/merged sectors (default false)
        sort: Sort order - name, activity, competence, success (default name)

    Returns:
        JSON array of sector objects
    """
    include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
    sort_by = request.args.get('sort', 'name')

    sectors = SectorService.get_user_sectors_list(current_user.id, include_inactive)

    # Apply sorting
    if sort_by == 'activity':
        sectors = sorted(sectors, key=lambda s: s.companies_analyzed, reverse=True)
    elif sort_by == 'competence':
        sectors = sorted(sectors, key=lambda s: s.coc_confidence, reverse=True)
    elif sort_by == 'success':
        sectors = sorted(sectors, key=lambda s: s.success_rate, reverse=True)
    # Default is name (already sorted by query)

    return jsonify([{
        'id': s.id,
        'name': s.name,
        'display_name': s.display_name,
        'slug': s.slug,
        'icon': s.icon,
        'color': s.color,
        'category': s.category,
        'status': s.status,
        'total_companies': s.total_companies,
        'companies_analyzed': s.companies_analyzed,
        'companies_invested': s.companies_invested,
        'coc_confidence': s.coc_confidence,
        'success_rate': s.success_rate,
        'competence_level': s.competence_level
    } for s in sectors])


@sectors_bp.route('/api/sectors', methods=['POST'])
@login_required
def create_sector():
    """
    Create a new sector.

    Request body (JSON):
        name: Sector name (required)
        display_name: Display name (optional, defaults to name)
        description: Description (optional)
        category: Category (optional)
        icon: Icon (optional)
        color: Color (optional)

    Returns:
        JSON with created sector object
    """
    data = request.get_json()

    if not data or 'name' not in data:
        return json_error('Sector name is required')

    name = data['name'].strip()
    if not name:
        return json_error('Sector name cannot be empty')

    # Check if sector already exists
    existing = SectorService.find_or_create_sector(current_user.id, name, auto_create=False)
    if existing:
        return jsonify({
            'error': 'Sector already exists',
            'existing_sector': {
                'id': existing.id,
                'display_name': existing.display_name,
                'slug': existing.slug
            }
        }), 409

    # Create new sector
    sector = Sector(
        user_id=current_user.id,
        name=name,
        display_name=data.get('display_name', name.title()),
        slug=Sector.make_slug(name),
        description=data.get('description'),
        category=data.get('category'),
        icon=data.get('icon'),
        color=data.get('color'),
        is_default=False
    )

    db.session.add(sector)
    db.session.commit()

    return jsonify({
        'id': sector.id,
        'name': sector.name,
        'display_name': sector.display_name,
        'slug': sector.slug,
        'message': 'Sector created successfully'
    }), 201


@sectors_bp.route('/api/sectors/<int:sector_id>', methods=['GET'])
@login_required
def get_sector(sector_id):
    """
    Get details for a specific sector.

    Returns:
        JSON with sector details and statistics
    """
    sector = Sector.query.get_or_404(sector_id)

    # Security check
    if sector.user_id != current_user.id:
        return json_unauthorized('Unauthorized')

    # Update analytics
    sector.update_analytics()

    # Get detailed stats
    stats = SectorService.get_sector_stats(sector_id, current_user.id)

    return jsonify({
        'id': sector.id,
        'name': sector.name,
        'display_name': sector.display_name,
        'slug': sector.slug,
        'description': sector.description,
        'category': sector.category,
        'icon': sector.icon,
        'color': sector.color,
        'key_characteristics': sector.key_characteristics,
        'typical_metrics': sector.typical_metrics,
        'aliases': sector.aliases,
        'status': sector.status,
        'is_default': sector.is_default,
        'statistics': stats
    })


@sectors_bp.route('/api/sectors/<int:sector_id>', methods=['PATCH'])
@login_required
def update_sector(sector_id):
    """
    Update sector metadata.

    Request body (JSON):
        Any of: display_name, description, category, icon, color,
               key_characteristics, typical_metrics, aliases

    Returns:
        JSON with updated sector
    """
    data = request.get_json()
    if not data:
        return json_error('No data provided')

    sector = SectorService.update_sector_metadata(current_user.id, sector_id, **data)

    if not sector:
        return json_error('Sector not found or unauthorized', status_code=404)

    return jsonify({
        'id': sector.id,
        'display_name': sector.display_name,
        'description': sector.description,
        'message': 'Sector updated successfully'
    })


@sectors_bp.route('/api/sectors/<int:sector_id>/archive', methods=['POST'])
@login_required
def archive_sector_api(sector_id):
    """
    Archive a sector (soft delete).

    Returns:
        JSON with success message
    """
    success = SectorService.archive_sector(current_user.id, sector_id)

    if not success:
        return json_error('Sector not found or unauthorized', status_code=404)

    return jsonify({'message': 'Sector archived successfully'})


@sectors_bp.route('/api/sectors/<int:sector_id>/restore', methods=['POST'])
@login_required
def restore_sector_api(sector_id):
    """
    Restore an archived sector.

    Returns:
        JSON with success message
    """
    success = SectorService.restore_sector(current_user.id, sector_id)

    if not success:
        return json_error('Sector not found or unauthorized', status_code=404)

    return jsonify({'message': 'Sector restored successfully'})


@sectors_bp.route('/api/sectors/merge', methods=['POST'])
@login_required
def merge_sectors():
    """
    Merge two sectors together.

    Request body (JSON):
        source_sector_id: ID of sector to merge from
        target_sector_id: ID of sector to merge into

    Returns:
        JSON with success message
    """
    data = request.get_json()

    if not data or 'source_sector_id' not in data or 'target_sector_id' not in data:
        return json_error('source_sector_id and target_sector_id are required')

    source_id = data['source_sector_id']
    target_id = data['target_sector_id']

    if source_id == target_id:
        return json_error('Cannot merge sector with itself')

    success = SectorService.merge_sectors(current_user.id, source_id, target_id)

    if not success:
        return json_error('Failed to merge sectors. Check permissions and IDs.')

    return jsonify({
        'message': 'Sectors merged successfully',
        'target_sector_id': target_id
    })


@sectors_bp.route('/api/sectors/<int:sector_id>/analytics', methods=['GET'])
@login_required
def get_sector_analytics(sector_id):
    """
    Get comprehensive analytics for a sector.

    Returns:
        JSON with detailed sector analytics
    """
    sector = SectorService.get_sector_analytics(current_user.id, sector_id)

    if not sector:
        return json_error('Sector not found', status_code=404)

    stats = SectorService.get_sector_stats(sector_id, current_user.id)

    return jsonify({
        'sector_id': sector_id,
        'display_name': sector.display_name,
        'analytics': {
            'total_companies': sector.total_companies,
            'companies_analyzed': sector.companies_analyzed,
            'companies_invested': sector.companies_invested,
            'total_research_hours': sector.total_research_hours,
            'success_rate': sector.success_rate,
            'coc_confidence': sector.coc_confidence,
            'competence_level': sector.competence_level,
            'circle_of_competence': {
                'yes': sector.coc_yes_count,
                'no': sector.coc_no_count,
                'unsure': sector.coc_unsure_count
            },
            'detailed_stats': stats
        }
    })


@sectors_bp.route('/api/sectors/analytics', methods=['GET'])
@login_required
def get_all_sectors_analytics():
    """
    Get analytics for all user's sectors.

    Returns:
        JSON with categorized sector analytics
    """
    analytics = SectorService.get_sector_analytics(current_user.id)

    # Convert to JSON-serializable format
    result = {
        'total_sectors': analytics['total_sectors'],
        'active_research': analytics['active_research'],
        'sectors': {
            'all': [{
                'id': s.id,
                'display_name': s.display_name,
                'companies_analyzed': s.companies_analyzed,
                'success_rate': s.success_rate,
                'coc_confidence': s.coc_confidence,
                'competence_level': s.competence_level
            } for s in analytics['all']],
            'by_competence': [{
                'id': s.id,
                'display_name': s.display_name,
                'coc_confidence': s.coc_confidence,
                'competence_level': s.competence_level
            } for s in analytics['by_competence'][:10]],  # Top 10
            'by_success': [{
                'id': s.id,
                'display_name': s.display_name,
                'success_rate': s.success_rate,
                'companies_invested': s.companies_invested
            } for s in analytics['by_success'][:10]],  # Top 10
            'by_activity': [{
                'id': s.id,
                'display_name': s.display_name,
                'companies_analyzed': s.companies_analyzed,
                'total_research_hours': s.total_research_hours
            } for s in analytics['by_activity'][:10]]  # Top 10
        }
    }

    return jsonify(result)


@sectors_bp.route('/api/send-to-sector', methods=['POST'])
@login_required
def send_to_sector():
    """
    Send content from company research to a sector notebook's Research Canvas.

    Creates a SectorNote linked to the source company.
    If the sector or its analysis notebook doesn't exist yet, creates them on the fly.

    Request body (JSON):
        sector_name: Name of the sector notebook (required)
        content: The text content to send (required)
        title: Title for the note (required)
        company_id: ID of the source company (required)
        section_id: Canvas section ID to file under (optional, null = inbox)
        context_note: Optional context about why this is sector-relevant
        source_page: Which page sent this (e.g. 'free_research', 'position_detail', 'thesis')
        source_detail: Extra detail (e.g. step name, question text)

    Returns:
        JSON with created note and sector notebook URL
    """
    data = request.get_json()
    if not data:
        return json_error('No data provided')

    sector_name = (data.get('sector_name') or '').strip()
    content = (data.get('content') or '').strip()
    title = (data.get('title') or '').strip()
    company_id = data.get('company_id')

    if not sector_name:
        return json_error('Sector name is required')
    if not content:
        return json_error('Content is required')
    if not title:
        return json_error('Title is required')
    if not company_id:
        return json_error('Company ID is required')

    # Verify company belongs to user
    company = Company.query.filter_by(id=company_id, user_id=current_user.id).first()
    if not company:
        return json_error('Company not found', status_code=404)

    # Find or create sector
    sector = SectorService.find_or_create_sector(current_user.id, sector_name, auto_create=True)
    if not sector:
        return json_error('Failed to create sector')

    # Find or create sector analysis
    analysis = SectorAnalysis.query.filter_by(
        user_id=current_user.id,
        sector_id=sector.id
    ).first()

    if not analysis:
        analysis = SectorAnalysis(
            user_id=current_user.id,
            sector_id=sector.id
        )
        db.session.add(analysis)
        db.session.flush()
        initialize_default_sections(analysis)

    # Resolve section_id
    section_id = data.get('section_id')
    if section_id in ('', 'null', None, 0):
        section_id = None
    else:
        section_id = int(section_id)
        section = SectorSection.query.filter_by(id=section_id, sector_analysis_id=analysis.id).first()
        if not section:
            section_id = None

    # Build source info
    source_detail = data.get('source_detail', '')
    source_title = f"From {company.ticker_symbol or company.name}"
    if source_detail:
        source_title += f" - {source_detail}"

    source_reference = url_for('companies.company_detail', company_id=company.id, _external=True)

    # Build full content (append context note if provided)
    context_note = (data.get('context_note') or '').strip()
    full_content = content
    if context_note:
        full_content += f"\n\n---\n**Context:** {context_note}"

    # Get max sort_order for target section
    if section_id:
        max_order = db.session.query(func.max(SectorNote.sort_order)).filter_by(
            section_id=section_id
        ).scalar() or 0
    else:
        max_order = 0

    try:
        note = SectorNote(
            sector_analysis_id=analysis.id,
            section_id=section_id,
            title=title,
            content=full_content,
            note_type='company_insight',
            source_reference=source_reference,
            source_title=source_title,
            tags=company.ticker_symbol or '',
            sort_order=max_order + 1
        )
        db.session.add(note)
        db.session.flush()

        # Link company via M2M
        note.linked_companies.append(company)

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return json_error(f'Failed to save note: {str(e)}', status_code=500)

    notebook_url = url_for('sectors.notebook', sector_name=sector.slug)

    return jsonify({
        'success': True,
        'item': {
            'id': note.id,
            'title': note.title,
            'section_id': note.section_id,
            'note_type': note.note_type,
            'created_at': note.created_at.isoformat()
        },
        'sector': {
            'id': sector.id,
            'display_name': sector.display_name,
            'slug': sector.slug,
            'notebook_url': notebook_url
        }
    }), 201


@sectors_bp.route('/api/sector-sections', methods=['GET'])
@login_required
def get_sector_sections():
    """
    Get canvas sections for a sector, used by the Send to Sector modal.

    Query params:
        sector_name: Sector name or slug (required)

    Returns:
        JSON array of section objects, or empty array if sector/analysis doesn't exist yet
    """
    sector_name = request.args.get('sector_name', '').strip()
    if not sector_name:
        return jsonify([])

    # Try to find sector (don't auto-create just for fetching sections)
    sector = SectorService.find_or_create_sector(current_user.id, sector_name, auto_create=False)
    if not sector:
        return jsonify([])

    analysis = SectorAnalysis.query.filter_by(
        user_id=current_user.id,
        sector_id=sector.id
    ).first()

    if not analysis:
        return jsonify([])

    sections = SectorSection.query.filter_by(
        sector_analysis_id=analysis.id
    ).order_by(SectorSection.sort_order).all()

    return jsonify([{
        'id': s.id,
        'title': s.title,
        'icon': s.icon,
        'description': s.description
    } for s in sections])


# ============================================================================
# RESEARCH TIME TRACKING
# ============================================================================

# Upper bound on a single heartbeat increment. The client flushes roughly every
# 30s, so anything much larger than a couple of minutes indicates a stale or
# tampered payload and is rejected rather than trusted.
MAX_TRACK_TIME_SECONDS = 300


@sectors_bp.route('/api/sectors/analysis/<int:analysis_id>/track-time', methods=['POST'])
@login_required
def track_research_time(analysis_id):
    """Increment active research time for a sector analysis.

    Called periodically by the client-side heartbeat while the sector research
    page is open, visible, and the user is active. Each request adds a small
    number of seconds to ``total_time_spent``.
    """
    analysis = SectorAnalysis.query.filter_by(
        id=analysis_id, user_id=current_user.id
    ).first()

    if not analysis:
        return json_unauthorized('Access denied')

    data = request.get_json(silent=True) or {}

    try:
        seconds = int(data.get('seconds', 0))
    except (TypeError, ValueError):
        return json_error('Invalid seconds value')

    if seconds <= 0 or seconds > MAX_TRACK_TIME_SECONDS:
        return json_error('Invalid seconds value')

    analysis.total_time_spent = (analysis.total_time_spent or 0) + seconds

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return json_error(str(e), status_code=500)

    return jsonify({
        'success': True,
        'total_time_spent': analysis.total_time_spent,
        'time_spent_formatted': analysis.time_spent_formatted,
    })
