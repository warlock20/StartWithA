# app/sectors/api_routes.py

from flask import jsonify, request
from flask_login import current_user, login_required
from app import db
from app.models import Sector
from app.services.sector_service import SectorService
from app.sectors import sectors_bp


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
        return jsonify({'error': 'Sector name is required'}), 400

    name = data['name'].strip()
    if not name:
        return jsonify({'error': 'Sector name cannot be empty'}), 400

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
        return jsonify({'error': 'Unauthorized'}), 403

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
        return jsonify({'error': 'No data provided'}), 400

    sector = SectorService.update_sector_metadata(current_user.id, sector_id, **data)

    if not sector:
        return jsonify({'error': 'Sector not found or unauthorized'}), 404

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
        return jsonify({'error': 'Sector not found or unauthorized'}), 404

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
        return jsonify({'error': 'Sector not found or unauthorized'}), 404

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
        return jsonify({'error': 'source_sector_id and target_sector_id are required'}), 400

    source_id = data['source_sector_id']
    target_id = data['target_sector_id']

    if source_id == target_id:
        return jsonify({'error': 'Cannot merge sector with itself'}), 400

    success = SectorService.merge_sectors(current_user.id, source_id, target_id)

    if not success:
        return jsonify({'error': 'Failed to merge sectors. Check permissions and IDs.'}), 400

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
        return jsonify({'error': 'Sector not found'}), 404

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
