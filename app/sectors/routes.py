from flask import render_template, request, redirect, url_for, flash, jsonify, current_app
from app.utils.response_utils import json_success, json_error, json_not_found, json_unauthorized
from flask_login import current_user, login_required
from app import db
from app.models import (SectorAnalysis, QuestionBankItem, SectorResearchSection,
                       Company, ResearchProject, SectorResearchSource, SectorResearchSnippet,
                       SectorSection, SectorNote)
from app.models.associations import sector_note_companies, sector_snippet_companies
from app.services.sector_service import SectorService
from app.services.too_hard_service import TooHardBasketService
from app.utils.time_utils import now_utc
from sqlalchemy import func
import re
from . import sectors_bp
from .research_templates import get_all_templates, get_template_list, get_template
from app.services.ai import ai_service
from app.services.sector_service import SectorService
from app.models.sector import Sector as SectorModel

def get_sector_by_name_or_slug(sector_name, user_id, redirect_to_canonical=False):
    """
    Helper function to look up a Sector object by slug or display name.

    Args:
        sector_name: Slug or display name to search for
        user_id: User ID
        redirect_to_canonical: If True, returns (sector, should_redirect) tuple

    Returns:
        Sector object or None if not found
        OR (Sector, bool) tuple if redirect_to_canonical=True
    """

    # Normalize the input to create a potential slug
    potential_slug = SectorModel.make_slug(sector_name)

    # Try by slug first (canonical)
    sector = SectorModel.query.filter_by(user_id=user_id, slug=potential_slug).first()

    if sector:
        # Found by slug - this is the canonical URL
        if redirect_to_canonical:
            return sector, False  # No redirect needed
        return sector

    # Try by display_name as fallback
    sector = SectorModel.query.filter_by(user_id=user_id, display_name=sector_name).first()

    if sector and redirect_to_canonical:
        # Found by display_name - should redirect to slug
        return sector, True

    return sector if not redirect_to_canonical else (None, False)


def initialize_default_sections(sector_analysis):
    """
    Create default research sections for a new sector analysis.
    These can be customized, reordered, or removed by users in the future.
    """
    default_sections = [
        {
            'title': 'Sector Overview & Scope',
            'icon': '📊',
            'description': 'Define the industry, market size, growth rate, and key segments',
            'section_type': 'overview',
            'display_order': 1,
            'is_locked': False
        },
        {
            'title': 'Industry Analysis',
            'icon': '🔍',
            'description': 'Analyze competitive dynamics, barriers to entry, supplier/buyer power, and threat of substitutes',
            'section_type': 'analysis',
            'display_order': 2,
            'is_locked': False
        },
        {
            'title': 'Current Trends & Catalysts',
            'icon': '📈',
            'description': 'Document technological disruptions, regulatory changes, and market shifts',
            'section_type': 'trends',
            'display_order': 3,
            'is_locked': False
        },
        {
            'title': 'Risks & Challenges',
            'icon': '⚠️',
            'description': 'Identify cyclicality, regulatory risks, competitive threats, and headwinds',
            'section_type': 'risks',
            'display_order': 4,
            'is_locked': False
        },
        {
            'title': 'Investment Opportunities',
            'icon': '💎',
            'description': 'Key subsectors to focus on, what to look for in companies, and investment thesis',
            'section_type': 'opportunities',
            'display_order': 5,
            'is_locked': False
        },
        {
            'title': 'Additional Research Notes',
            'icon': '📝',
            'description': 'Free-form notes, sources, links, and miscellaneous research',
            'section_type': 'custom',
            'display_order': 6,
            'is_locked': False
        }
    ]

    for section_data in default_sections:
        section = SectorResearchSection(
            sector_analysis_id=sector_analysis.id,
            **section_data
        )
        db.session.add(section)

    db.session.commit()

@sectors_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        sector_name = request.form.get('sector_name')
        if not sector_name or not sector_name.strip():
            flash('Sector name is required.', 'error')
            return redirect(url_for('sectors.index'))

        # Find or create the Sector
        sector = SectorService.find_or_create_sector(current_user.id, sector_name.strip(), auto_create=True)

        # Check if an analysis for this sector already exists for the user
        existing = SectorAnalysis.query.filter_by(user_id=current_user.id, sector_id=sector.id).first()
        if existing:
            flash(f'You already have a research notebook for the "{sector.display_name}" sector.', 'info')
            return redirect(url_for('sectors.notebook', sector_name=sector.slug))

        new_analysis = SectorAnalysis(
            user_id=current_user.id,
            sector_id=sector.id
        )
        db.session.add(new_analysis)
        db.session.commit()

        # Initialize default research sections
        initialize_default_sections(new_analysis)

        flash(f'New research notebook for "{sector.display_name}" created.', 'success')
        return redirect(url_for('sectors.notebook', sector_name=sector.slug))


    # GET Request: Fetch and display all existing sector analyses
    # Get filter from query param (default to 'active')
    status_filter = request.args.get('status', 'active')

    if status_filter == 'archived':
        sector_analyses = SectorAnalysis.query.filter_by(
            user_id=current_user.id,
            status='archived'
        ).order_by(SectorAnalysis.archived_at.desc()).all()
    else:
        sector_analyses = SectorAnalysis.query.filter_by(
            user_id=current_user.id,
            status='active'
        ).order_by(SectorAnalysis.updated_at.desc()).all()

    # Count for tabs
    active_count = SectorAnalysis.query.filter_by(user_id=current_user.id, status='active').count()
    archived_count = SectorAnalysis.query.filter_by(user_id=current_user.id, status='archived').count()

    return render_template('list_sectors.html',
                           title="My Sector Research",
                           sector_analyses=sector_analyses,
                           status_filter=status_filter,
                           active_count=active_count,
                           archived_count=archived_count)
    
def _get_sector_and_analysis(sector_name, user_id):
    """Get and validate sector and analysis."""
    sector, should_redirect = get_sector_by_name_or_slug(sector_name, user_id, redirect_to_canonical=True)

    if not sector:
        return None, None, None

    if should_redirect:
        return sector, None, True

    analysis = SectorAnalysis.query.filter_by(user_id=user_id, sector_id=sector.id).first_or_404()

    if analysis.sections.count() == 0:
        initialize_default_sections(analysis)

    return sector, analysis, False


def _enrich_company(company, user_id, user_favorites):
    """Enrich single company with project and status info."""
    active_project = ResearchProject.query.filter_by(
        user_id=user_id,
        company_id=company.id,
        status='active'
    ).first()

    completed_project = ResearchProject.query.filter_by(
        user_id=user_id,
        company_id=company.id,
        status='completed'
    ).first()

    return {
        'company': company,
        'active_project': active_project,
        'completed_project': completed_project,
        'is_in_watchlist': company in user_favorites,
        'is_in_portfolio': company.is_in_portfolio
    }


def _get_companies_data(analysis, user_id, user_favorites):
    """Get companies in sector with enriched data."""
    companies = Company.query.filter_by(user_id=user_id, sector_id=analysis.sector_id).all()
    return [_enrich_company(c, user_id, user_favorites) for c in companies]


def _get_other_companies(sector_id, user_id):
    """Get companies not in this sector."""
    return Company.query.filter(
        Company.user_id == user_id,
        db.or_(Company.sector_id != sector_id, Company.sector_id.is_(None))
    ).order_by(Company.name).all()


def _calculate_sector_metrics(companies_data):
    """Calculate sector metrics from companies data."""
    return {
        'total': len(companies_data),
        'researched': sum(1 for c in companies_data if c['completed_project']),
        'watchlist': sum(1 for c in companies_data if c['is_in_watchlist']),
        'portfolio': sum(1 for c in companies_data if c['is_in_portfolio'])
    }


def _get_sources_data(analysis):
    """Get sources and group by type."""
    sources = analysis.sources.order_by(SectorResearchSource.created_at.desc()).all()

    sources_by_type = {}
    for source in sources:
        source_type = source.source_type
        if source_type not in sources_by_type:
            sources_by_type[source_type] = []
        sources_by_type[source_type].append(source)

    return sources, sources_by_type


def _get_canvas_data(analysis):
    """Get canvas sections and collector notes."""
    canvas_sections = analysis.canvas_sections.order_by(SectorSection.sort_order).all()
    collector_notes = analysis.canvas_notes.filter(
        SectorNote.section_id == None
    ).order_by(SectorNote.created_at.desc()).all()

    return canvas_sections, collector_notes


def _get_passed_companies_data(sector, user_id):
    """Get Too Hard Basket companies for this sector."""
    if not sector:
        return []

    all_too_hard = TooHardBasketService.get_all_too_hard_companies(user_id, {})
    sector_passed = [item for item in all_too_hard if item.sector == sector.display_name]

    return [{
        'company_name': item.company_name,
        'ticker': item.ticker,
        'rejection_stage': item.rejection_stage,
        'rejection_date': item.rejection_date,
        'time_invested_hours': item.time_invested_hours,
        'reason': item.reason,
        'within_coc': item.within_coc,
        'confidence': item.confidence,
        'notes': item.notes,
        'source_type': item.source_type,
        'source_id': item.source_id,
        'company_id': item.company_id
    } for item in sector_passed]


@sectors_bp.route('/<string:sector_name>', methods=['GET', 'POST'])
@login_required
def notebook(sector_name):
    """Main sector research page."""
    sector, analysis, should_redirect = _get_sector_and_analysis(sector_name, current_user.id)

    if not sector:
        flash('Sector not found', 'error')
        return redirect(url_for('sectors.list_sectors'))

    if should_redirect:
        return redirect(url_for('sectors.notebook', sector_name=sector.slug), code=301)

    # Auto-track sector review: Update last_researched when user views sector
    sector.last_researched = now_utc()
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        # Don't fail the request if tracking fails
        pass

    if request.method == 'POST':
        flash('Please use the Document View or Research Canvas to save your notes.', 'info')
        return redirect(url_for('sectors.notebook', sector_name=sector.slug))

    # Build page data using helper functions
    question_bank_items = QuestionBankItem.query.filter_by(
        user_id=current_user.id,
        sector_id=sector.id
    ).order_by(QuestionBankItem.created_at.desc()).all()

    sections = analysis.sections.filter_by(is_visible=True).all()
    user_favorites = current_user.favorites.all()
    companies_data = _get_companies_data(analysis, current_user.id, user_favorites)
    other_companies = _get_other_companies(sector.id, current_user.id)
    sector_metrics = _calculate_sector_metrics(companies_data)
    sources, sources_by_type = _get_sources_data(analysis)
    canvas_sections, collector_notes = _get_canvas_data(analysis)
    sector_stats = SectorService.get_sector_stats(sector.id, current_user.id)
    passed_companies = _get_passed_companies_data(sector, current_user.id)

    return render_template(
        'sector_analysis.html',
        title=f"Research: {analysis.sector.display_name}",
        analysis=analysis,
        question_bank_items=question_bank_items,
        sections=sections,
        companies_data=companies_data,
        other_companies=other_companies,
        sector_metrics=sector_metrics,
        sources=sources,
        sources_by_type=sources_by_type,
        canvas_sections=canvas_sections,
        collector_notes=collector_notes,
        research_templates=get_all_templates(),
        template_list=get_template_list(),
        sector_stats=sector_stats,
        passed_companies=passed_companies
    )


@sectors_bp.route('/<string:sector_name>/focus')
@login_required
def sector_analysis_focus(sector_name):
    """Focus mode - distraction-free sector research interface."""
    sector, analysis, should_redirect = _get_sector_and_analysis(sector_name, current_user.id)

    if not sector:
        flash('Sector not found', 'error')
        return redirect(url_for('sectors.index'))

    if should_redirect:
        return redirect(url_for('sectors.sector_analysis_focus', sector_name=sector.slug), code=301)

    # Auto-track sector review: Update last_researched when user views sector
    sector.last_researched = now_utc()
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        # Don't fail the request if tracking fails
        pass

    # Build page data using same helper functions as notebook route
    question_bank_items = QuestionBankItem.query.filter_by(
        user_id=current_user.id,
        sector_id=sector.id
    ).order_by(QuestionBankItem.created_at.desc()).all()

    sections = analysis.sections.filter_by(is_visible=True).all()
    user_favorites = current_user.favorites.all()
    companies_data = _get_companies_data(analysis, current_user.id, user_favorites)
    other_companies = _get_other_companies(sector.id, current_user.id)
    sector_metrics = _calculate_sector_metrics(companies_data)
    sources, sources_by_type = _get_sources_data(analysis)
    canvas_sections, collector_notes = _get_canvas_data(analysis)
    sector_stats = SectorService.get_sector_stats(sector.id, current_user.id)
    passed_companies = _get_passed_companies_data(sector, current_user.id)

    return render_template(
        'sector_analysis_focus.html',  # Focus mode template
        title=f"Focus Mode: {analysis.sector.display_name}",
        analysis=analysis,
        question_bank_items=question_bank_items,
        sections=sections,
        companies_data=companies_data,
        other_companies=other_companies,
        sector_metrics=sector_metrics,
        sources=sources,
        sources_by_type=sources_by_type,
        canvas_sections=canvas_sections,
        collector_notes=collector_notes,
        research_templates=get_all_templates(),
        template_list=get_template_list(),
        sector_stats=sector_stats,
        passed_companies=passed_companies
    )


@sectors_bp.route('/<string:sector_name>/add_question', methods=['POST'])
@login_required
def add_question_to_bank(sector_name):
    """Add a new question to the bank from the sector notebook page."""
    sector = get_sector_by_name_or_slug(sector_name, current_user.id)
    if not sector:
        flash('Sector not found', 'error')
        return redirect(url_for('sectors.index'))

    SectorAnalysis.query.filter_by(user_id=current_user.id, sector_id=sector.id).first_or_404()

    text = request.form.get('text')
    llm_prompt = request.form.get('llm_prompt')

    if not text:
        flash('Question text is required.', 'error')
    else:
        new_question = QuestionBankItem(
            user_id=current_user.id,
            text=text,
            llm_prompt=llm_prompt.strip() if llm_prompt and llm_prompt.strip() else None,
            sector_id=sector.id
        )
        db.session.add(new_question)
        db.session.commit()
        flash('New question added to your bank for this sector.', 'success')

    return redirect(url_for('sectors.notebook', sector_name=sector_name))

@sectors_bp.route('/question_bank_item/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_question_from_bank(item_id):
    """Delete a question from the bank, redirecting back to the notebook page."""
    question = QuestionBankItem.query.get_or_404(item_id)
    if question.user_id != current_user.id:
        flash('You are not authorized to delete this item.', 'error')
        return redirect(url_for('sectors.index'))

    # Get sector slug for redirect before deleting
    sector_slug = question.sector.slug if question.sector else None
    db.session.delete(question)
    db.session.commit()
    flash('Question deleted from your bank.', 'success')

    if sector_slug:
        return redirect(url_for('sectors.notebook', sector_name=sector_slug))
    else:
        return redirect(url_for('question_bank.index'))
    
@sectors_bp.route('/<int:analysis_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_sector(analysis_id):
    analysis = SectorAnalysis.query.get_or_404(analysis_id)
    # Authorization check
    if analysis.user_id != current_user.id:
        flash("You are not authorized to edit this sector analysis.", "error")
        return redirect(url_for('sectors.index'))

    if request.method == 'POST':
        new_sector_name = request.form.get('sector_name', '').strip()

        if not new_sector_name:
            flash("Sector name cannot be empty.", "error")
            return render_template('edit_sector.html', title="Edit Sector", analysis=analysis)

        # Get the current sector
        from app.models.sector import Sector as SectorModel
        from app.services.sector_service import SectorService

        old_sector = analysis.sector

        # Find or create the new sector
        new_sector = SectorService.find_or_create_sector(current_user.id, new_sector_name, auto_create=True)

        # Check if a notebook with this sector already exists for this user
        if new_sector.id != old_sector.id:
            existing = SectorAnalysis.query.filter(
                SectorAnalysis.user_id == current_user.id,
                SectorAnalysis.sector_id == new_sector.id,
                SectorAnalysis.id != analysis.id # Exclude the current one
            ).first()

            if existing:
                flash(f"You already have a research notebook for '{new_sector.display_name}'.", "error")
                return render_template('edit_sector.html', title="Edit Sector", analysis=analysis)

            # Update the analysis to point to the new sector
            analysis.sector_id = new_sector.id

            # Update question bank items to use the new sector
            QuestionBankItem.query.filter_by(
                user_id=current_user.id,
                sector_id=old_sector.id
            ).update({'sector_id': new_sector.id})

        # Update the sector display name if it's the same sector
        else:
            old_sector.display_name = new_sector_name

        try:
            db.session.commit()
            flash("Sector analysis updated successfully.", "success")
            # Redirect to the notebook page with the NEW slug
            return redirect(url_for('sectors.notebook', sector_name=new_sector.slug))
        except Exception as e:
            db.session.rollback()
            flash(f"An error occurred: {e}", "error")
        
        next_url = request.args.get('next')
        if next_url:
            return redirect(next_url)
        else:
            return redirect(url_for('question_bank.index'))

    # GET request
    return render_template('edit_sector.html', title="Edit Sector", analysis=analysis)


@sectors_bp.route('/section/<int:section_id>/save', methods=['POST'])
@login_required
def save_section(section_id):
    """
    API endpoint to save a section's content via AJAX.
    Supports auto-save functionality from Quill.js editor.
    """
    section = SectorResearchSection.query.get_or_404(section_id)

    # Authorization check
    if section.sector_analysis.author != current_user:
        return json_unauthorized('Unauthorized')

    # Get content from request
    content = request.json.get('content', '')

    # Update section
    section.content = content
    section.updated_at = db.func.now()  # Explicitly update timestamp

    try:
        db.session.commit()
        return jsonify({
            'success': True,
            'word_count': section.word_count,
            'updated_at': section.updated_at.strftime('%b %d, %Y %I:%M %p')
        })
    except Exception as e:
        db.session.rollback()
        return json_error(str(e), status_code=500)


@sectors_bp.route('/<string:sector_name>/add_company/<int:company_id>', methods=['POST'])
@login_required
def add_company_to_sector(sector_name, company_id):
    """Add a company to this sector"""
    sector = get_sector_by_name_or_slug(sector_name, current_user.id)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if not sector:
        if is_ajax:
            return json_not_found('Sector')
        flash('Sector not found', 'error')
        return redirect(url_for('sectors.index'))

    analysis = SectorAnalysis.query.filter_by(user_id=current_user.id, sector_id=sector.id).first_or_404()
    company = Company.query.get_or_404(company_id)

    # Authorization check
    if company.user_id != current_user.id:
        if is_ajax:
            return json_unauthorized('Access denied')
        flash('Access denied', 'error')
        return redirect(url_for('sectors.notebook', sector_name=sector_name))

    # Update company sector
    company.sector_id = sector.id
    db.session.commit()

    if is_ajax:
        return jsonify({
            'success': True,
            'company': {
                'id': company.id,
                'name': company.name,
                'ticker': company.ticker_symbol or '',
                'is_in_portfolio': company.is_in_portfolio,
                'dashboard_url': url_for('companies.company_dashboard', company_id=company.id),
                'remove_url': url_for('sectors.remove_company_from_sector', sector_name=sector_name, company_id=company.id),
            }
        })

    flash(f'{company.name} added to {sector.display_name} sector', 'success')
    return redirect(url_for('sectors.notebook', sector_name=sector_name))


@sectors_bp.route('/<string:sector_name>/remove_company/<int:company_id>', methods=['POST'])
@login_required
def remove_company_from_sector(sector_name, company_id):
    """Remove a company from this sector"""
    sector = get_sector_by_name_or_slug(sector_name, current_user.id)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if not sector:
        if is_ajax:
            return json_not_found('Sector')
        flash('Sector not found', 'error')
        return redirect(url_for('sectors.index'))

    analysis = SectorAnalysis.query.filter_by(user_id=current_user.id, sector_id=sector.id).first_or_404()
    company = Company.query.get_or_404(company_id)

    # Authorization check
    if company.user_id != current_user.id:
        if is_ajax:
            return json_unauthorized('Access denied')
        flash('Access denied', 'error')
        return redirect(url_for('sectors.notebook', sector_name=sector_name))

    # Clear company sector
    company.sector_id = None
    db.session.commit()

    if is_ajax:
        return jsonify({
            'success': True,
            'company': {
                'id': company.id,
                'name': company.name,
            }
        })

    flash(f'{company.name} removed from {sector.display_name} sector', 'success')
    return redirect(url_for('sectors.notebook', sector_name=sector_name))


@sectors_bp.route('/<string:sector_name>/add_source', methods=['POST'])
@login_required
def add_source(sector_name):
    """Add a research source/reference"""
    sector = get_sector_by_name_or_slug(sector_name, current_user.id)
    if not sector:
        flash('Sector not found', 'error')
        return redirect(url_for('sectors.index'))

    analysis = SectorAnalysis.query.filter_by(user_id=current_user.id, sector_id=sector.id).first_or_404()

    # Get form data
    title = request.form.get('title', '').strip()
    url = request.form.get('url', '').strip()
    source_type = request.form.get('source_type', 'article')
    description = request.form.get('description', '').strip()

    if not title:
        flash('Source title is required', 'error')
        return redirect(url_for('sectors.notebook', sector_name=sector_name))

    # Create new source
    source = SectorResearchSource(
        sector_analysis_id=analysis.id,
        title=title,
        url=url if url else None,
        source_type=source_type,
        description=description if description else None
    )

    db.session.add(source)
    db.session.commit()

    flash(f'Source "{title}" added successfully', 'success')
    return redirect(url_for('sectors.notebook', sector_name=sector_name))


@sectors_bp.route('/source/<int:source_id>/delete', methods=['POST'])
@login_required
def delete_source(source_id):
    """Delete a research source"""
    source = SectorResearchSource.query.get_or_404(source_id)

    # Authorization check
    if source.sector_analysis.author != current_user:
        flash('Access denied', 'error')
        return redirect(url_for('sectors.index'))

    sector_slug = source.sector_analysis.sector.slug
    db.session.delete(source)
    db.session.commit()

    flash('Source deleted', 'success')
    return redirect(url_for('sectors.notebook', sector_name=sector_slug))


@sectors_bp.route('/source/<int:source_id>/mark_accessed', methods=['POST'])
@login_required
def mark_source_accessed(source_id):
    """Mark a source as accessed (update accessed_at timestamp)"""
    source = SectorResearchSource.query.get_or_404(source_id)

    # Authorization check
    if source.sector_analysis.author != current_user:
        return json_unauthorized('Unauthorized')

    source.accessed_at = now_utc()
    db.session.commit()

    return json_success()


@sectors_bp.route('/<string:sector_name>/add_snippet', methods=['POST'])
@login_required
def add_snippet(sector_name):
    """Add a research snippet"""
    sector = get_sector_by_name_or_slug(sector_name, current_user.id)
    if not sector:
        return json_not_found('Sector')

    analysis = SectorAnalysis.query.filter_by(
        user_id=current_user.id,
        sector_id=sector.id
    ).first_or_404()

    data = request.get_json()
    content = data.get('content', '').strip()
    category = data.get('category', '').strip()
    tags = data.get('tags', '').strip()
    notes = data.get('notes', '').strip()

    if not content or not category:
        return json_error('Content and category are required')

    # Create new snippet
    snippet = SectorResearchSnippet(
        sector_analysis_id=analysis.id,
        content=content,
        category=category,
        tags=tags if tags else None,
        notes=notes if notes else None
    )

    db.session.add(snippet)
    db.session.commit()

    return jsonify({'success': True, 'snippet_id': snippet.id})


@sectors_bp.route('/snippet/<int:snippet_id>/delete', methods=['POST'])
@login_required
def delete_snippet(snippet_id):
    """Delete a research snippet"""
    snippet = SectorResearchSnippet.query.get_or_404(snippet_id)

    # Authorization check
    if snippet.sector_analysis.author != current_user:
        return json_unauthorized('Unauthorized')

    sector_slug = snippet.sector_analysis.sector.slug
    db.session.delete(snippet)
    db.session.commit()

    flash('Snippet deleted', 'success')
    return redirect(url_for('sectors.notebook', sector_name=sector_slug))


# ============================================================================
# ATOMIC NOTES CANVAS ROUTES
# ============================================================================

@sectors_bp.route('/<string:sector_name>/section/create', methods=['POST'])
@login_required
def create_section(sector_name):
    """Create a new section on the canvas"""
    sector = get_sector_by_name_or_slug(sector_name, current_user.id)
    if not sector:
        return json_not_found('Sector')

    analysis = SectorAnalysis.query.filter_by(
        user_id=current_user.id,
        sector_id=sector.id
    ).first_or_404()

    data = request.get_json()
    title = data.get('title', '').strip()

    if not title:
        return json_error('Title is required')

    # Get max sort_order
    max_order = db.session.query(func.max(SectorSection.sort_order)).filter_by(
        sector_analysis_id=analysis.id
    ).scalar() or 0

    section = SectorSection(
        sector_analysis_id=analysis.id,
        title=title,
        description=data.get('description'),
        sort_order=max_order + 1,
        icon=data.get('icon'),
        color=data.get('color')
    )

    db.session.add(section)
    db.session.commit()

    return jsonify({
        'success': True,
        'section': {
            'id': section.id,
            'title': section.title,
            'description': section.description,
            'sort_order': section.sort_order
        }
    })


@sectors_bp.route('/section/<int:section_id>/update', methods=['POST'])
@login_required
def update_section(section_id):
    """Update a section"""
    section = SectorSection.query.get_or_404(section_id)

    if section.sector_analysis.author != current_user:
        return json_unauthorized('Unauthorized')

    data = request.get_json()

    if 'title' in data:
        section.title = data['title'].strip()
    if 'description' in data:
        section.description = data.get('description')
    if 'icon' in data:
        section.icon = data.get('icon')
    if 'color' in data:
        section.color = data.get('color')
    if 'sort_order' in data:
        section.sort_order = data['sort_order']

    db.session.commit()

    return json_success()


@sectors_bp.route('/section/<int:section_id>/delete', methods=['POST'])
@login_required
def delete_section(section_id):
    """Delete a section (notes will be moved to collector)"""
    section = SectorSection.query.get_or_404(section_id)

    if section.sector_analysis.author != current_user:
        return json_unauthorized('Unauthorized')

    # Move all notes in this section to collector (set section_id to None)
    SectorNote.query.filter_by(section_id=section_id).update({'section_id': None})

    db.session.delete(section)
    db.session.commit()

    return json_success()


@sectors_bp.route('/<string:sector_name>/note/create', methods=['POST'])
@login_required
def create_note(sector_name):
    """Create a new note"""
    sector = get_sector_by_name_or_slug(sector_name, current_user.id)
    if not sector:
        return json_not_found('Sector')

    analysis = SectorAnalysis.query.filter_by(
        user_id=current_user.id,
        sector_id=sector.id
    ).first_or_404()

    data = request.get_json(silent=True) or {}
    title = (data.get('title') or '').strip()
    content = (data.get('content') or '').strip()

    if not title or not content:
        return json_error('Title and content are required')

    section_id = data.get('section_id')
    if section_id in ('', 'null'):
        section_id = None

    try:
        # Get max sort_order for this section
        if section_id:
            max_order = db.session.query(func.max(SectorNote.sort_order)).filter_by(
                section_id=section_id
            ).scalar() or 0
        else:
            max_order = 0

        note = SectorNote(
            sector_analysis_id=analysis.id,
            section_id=section_id,
            title=title,
            content=content,
            note_type=data.get('note_type', 'note'),
            source_reference=data.get('source_reference'),
            source_title=data.get('source_title'),
            tags=data.get('tags'),
            sort_order=max_order + 1
        )

        db.session.add(note)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception('Failed to create sector note')
        return json_error(f'Failed to save note: {str(e)}', status_code=500)

    return jsonify({
        'success': True,
        'note': {
            'id': note.id,
            'title': note.title,
            'content': note.content,
            'note_type': note.note_type,
            'section_id': note.section_id,
            'created_at': note.created_at.isoformat()
        }
    })


@sectors_bp.route('/note/<int:note_id>/update', methods=['POST'])
@login_required
def update_note(note_id):
    """Update a note"""
    note = SectorNote.query.get_or_404(note_id)

    if note.sector_analysis.author != current_user:
        return json_unauthorized('Unauthorized')

    data = request.get_json(silent=True) or {}

    try:
        if 'title' in data:
            title = (data.get('title') or '').strip()
            if not title:
                return json_error('Title cannot be empty')
            note.title = title
        if 'content' in data:
            content = (data.get('content') or '').strip()
            if not content:
                return json_error('Content cannot be empty')
            note.content = content
        if 'section_id' in data:
            section_id = data.get('section_id')
            if section_id in ('', 'null'):
                section_id = None
            note.section_id = section_id
        if 'sort_order' in data:
            note.sort_order = data['sort_order']
        if 'tags' in data:
            note.tags = data.get('tags')
        if 'source_reference' in data:
            note.source_reference = data.get('source_reference')
        if 'source_title' in data:
            note.source_title = data.get('source_title')

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception('Failed to update sector note')
        return json_error(f'Failed to update note: {str(e)}', status_code=500)

    return json_success()


@sectors_bp.route('/note/<int:note_id>/delete', methods=['POST'])
@login_required
def delete_note(note_id):
    """Delete a note"""
    note = SectorNote.query.get_or_404(note_id)

    if note.sector_analysis.author != current_user:
        return json_unauthorized('Unauthorized')

    db.session.delete(note)
    db.session.commit()

    return json_success()


@sectors_bp.route('/<string:sector_name>/generate-document', methods=['GET'])
@login_required
def generate_document_from_canvas(sector_name):
    """Generate a formatted document from canvas sections and notes"""
    try:
        sector = get_sector_by_name_or_slug(sector_name, current_user.id)
        if not sector:
            return json_not_found('Sector')

        analysis = SectorAnalysis.query.filter_by(
            user_id=current_user.id,
            sector_id=sector.id
        ).first_or_404()

        # Get all sections in order
        sections = analysis.canvas_sections.order_by(SectorSection.sort_order).all()

        # Get collector notes (notes without section_id)
        collector_notes = analysis.canvas_notes.filter(SectorNote.section_id.is_(None)).order_by(SectorNote.created_at.desc()).all()

        # Build structured data for frontend to process
        sections_data = []
        for section in sections:
            # Get notes for this section
            notes = section.section_notes.order_by(SectorNote.sort_order).all()
            notes_list = list(notes) if hasattr(notes, '__iter__') else []

            section_data = {
                'id': section.id,
                'title': section.title,
                'icon': section.icon or '',
                'description': section.description or '',
                'notes_count': len(notes_list),
                'notes': [{
                    'id': note.id,
                    'title': note.title or '',
                    'content': note.content or '',
                    'source_reference': note.source_reference or '',
                    'source_title': note.source_title or '',
                    'tags': note.tags or ''
                } for note in notes_list]
            }
            sections_data.append(section_data)

        # Build collector data
        collector_data = [{
            'id': note.id,
            'title': note.title or '',
            'content': note.content or '',
            'source_reference': note.source_reference or '',
            'source_title': note.source_title or '',
            'tags': note.tags or ''
        } for note in collector_notes]

        return jsonify({
            'success': True,
            'sections': sections_data,
            'collector_notes': collector_data
        })

    except Exception as e:
        # Log the error for debugging
        import traceback
        print(f"Error in generate_document_from_canvas: {str(e)}")
        print(traceback.format_exc())

        return json_error(f'Server error: {str(e)}', status_code=500)


@sectors_bp.route('/<path:sector_name>/research-notes', methods=['GET'])
@login_required
def get_research_notes(sector_name):
    """Get research notes content for the simplified editor"""
    # Look up sector by slug
    from app.models.sector import Sector as SectorModel
    sector = SectorModel.query.filter_by(user_id=current_user.id, slug=sector_name).first()

    if not sector:
        # Try by display_name as fallback
        sector = SectorModel.query.filter_by(user_id=current_user.id, display_name=sector_name).first()

    if not sector:
        return json_not_found('Sector')

    analysis = SectorAnalysis.query.filter_by(
        user_id=current_user.id,
        sector_id=sector.id
    ).first_or_404()

    return jsonify({
        'success': True,
        'content': analysis.document_content or '',
        'takeaways': analysis.key_takeaways or ''
    })

@sectors_bp.route('/<path:sector_name>/research-notes', methods=['POST'])
@login_required
def save_research_notes(sector_name):
    """Save research notes content from the simplified editor"""
    # Look up sector by slug
    from app.models.sector import Sector as SectorModel
    sector = SectorModel.query.filter_by(user_id=current_user.id, slug=sector_name).first()

    if not sector:
        # Try by display_name as fallback
        sector = SectorModel.query.filter_by(user_id=current_user.id, display_name=sector_name).first()

    if not sector:
        return json_not_found('Sector')

    analysis = SectorAnalysis.query.filter_by(
        user_id=current_user.id,
        sector_id=sector.id
    ).first_or_404()

    data = request.get_json()
    content = data.get('content')
    takeaways = data.get('takeaways')

    if content is not None:
        analysis.document_content = content
    if takeaways is not None:
        analysis.key_takeaways = takeaways

    analysis.updated_at = now_utc()

    try:
        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'Document saved successfully'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@sectors_bp.route('/company/<int:company_id>/send-to-inbox', methods=['POST'])
@login_required
def send_company_to_inbox(company_id):
    """Send a company from sector research to idea inbox"""
    company = Company.query.get_or_404(company_id)

    # Authorization check
    if company.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('sectors.index'))

    # Check if already in inbox
    from app.models import IdeaPipeline
    existing_idea = IdeaPipeline.query.filter_by(
        user_id=current_user.id,
        company_id=company.id
    ).first()

    if existing_idea:
        flash(f'{company.name} is already in your idea pipeline', 'info')
    else:
        idea = IdeaPipeline(
            author=current_user,
            company_id=company.id,
            idea_name=company.name,
            idea_description=f"Added from {company.sector} sector research",
            status='inbox',
            source='sector_research'
        )
        db.session.add(idea)
        db.session.commit()
        flash(f'{company.name} added to Idea Inbox', 'success')

    # Redirect back to sector page
    if company.sector:
        return redirect(url_for('sectors.notebook', sector_name=company.sector))
    else:
        return redirect(url_for('sectors.index'))

@sectors_bp.route('/<string:sector_name>/archive', methods=['POST'])
@login_required
def archive_sector(sector_name):
    """Archive a sector research"""
    sector = get_sector_by_name_or_slug(sector_name, current_user.id)
    if not sector:
        flash('Sector not found', 'error')
        return redirect(url_for('sectors.index'))

    analysis = SectorAnalysis.query.filter_by(user_id=current_user.id, sector_id=sector.id).first_or_404()

    analysis.status = 'archived'
    analysis.archived_at = now_utc()
    db.session.commit()

    flash(f'{sector.display_name} sector research archived', 'success')
    return redirect(url_for('sectors.index'))

@sectors_bp.route('/<string:sector_name>/unarchive', methods=['POST'])
@login_required
def unarchive_sector(sector_name):
    """Unarchive a sector research"""
    sector = get_sector_by_name_or_slug(sector_name, current_user.id)
    if not sector:
        flash('Sector not found', 'error')
        return redirect(url_for('sectors.index'))

    analysis = SectorAnalysis.query.filter_by(user_id=current_user.id, sector_id=sector.id).first_or_404()

    analysis.status = 'active'
    analysis.archived_at = None
    db.session.commit()

    flash(f'{sector_name} sector research unarchived', 'success')
    return redirect(url_for('sectors.notebook', sector_name=sector_name))


@sectors_bp.route('/analysis/<int:analysis_id>/toggle-learning', methods=['POST'])
@login_required
def toggle_continuous_learning(analysis_id):
    """Toggle continuous learning tracking for a sector analysis"""
    analysis = SectorAnalysis.query.get_or_404(analysis_id)

    if analysis.user_id != current_user.id:
        return json_unauthorized('Unauthorized')

    data = request.get_json()
    enabled = data.get('enabled', False)

    analysis.continuous_learning_enabled = enabled

    try:
        db.session.commit()
        return jsonify({'success': True, 'enabled': enabled})
    except Exception as e:
        db.session.rollback()
        return json_error(str(e), status_code=500)


# ============================================================================
# COMPANY TAGGING ROUTES
# ============================================================================

@sectors_bp.route('/detect-companies', methods=['POST'])
@login_required
def detect_companies():
    """Detect company mentions in text and return suggestions"""
    from app.utils.company_detection import get_company_suggestions_for_text

    data = request.get_json()
    text = data.get('text', '')

    if not text or not text.strip():
        return json_error('No text provided')

    suggestions = get_company_suggestions_for_text(text, current_user.id)

    return jsonify({
        'success': True,
        'suggestions': suggestions
    })


@sectors_bp.route('/note/<int:note_id>/link-companies', methods=['POST'])
@login_required
def link_companies_to_note(note_id):
    """Link selected companies to a note"""
    note = SectorNote.query.get_or_404(note_id)

    # Authorization check
    if note.sector_analysis.author != current_user:
        return json_unauthorized('Unauthorized')

    data = request.get_json()
    company_ids = data.get('company_ids', [])

    if not company_ids:
        return json_error('No companies selected')

    # Verify all companies belong to the user
    companies = Company.query.filter(
        Company.id.in_(company_ids),
        Company.user_id == current_user.id
    ).all()

    if len(companies) != len(company_ids):
        return json_error('Invalid company IDs')

    # Clear existing links and add new ones
    # Delete existing associations
    db.session.execute(
        sector_note_companies.delete().where(
            sector_note_companies.c.sector_note_id == note_id
        )
    )

    # Add new associations
    for company in companies:
        db.session.execute(
            sector_note_companies.insert().values(
                sector_note_id=note_id,
                company_id=company.id
            )
        )

    db.session.commit()

    return jsonify({
        'success': True,
        'linked_companies': [{
            'id': c.id,
            'name': c.name,
            'ticker': c.ticker_symbol
        } for c in companies]
    })


@sectors_bp.route('/note/<int:note_id>/unlink-company/<int:company_id>', methods=['POST'])
@login_required
def unlink_company_from_note(note_id, company_id):
    """Remove a specific company link from a note"""
    note = SectorNote.query.get_or_404(note_id)

    # Authorization check
    if note.sector_analysis.author != current_user:
        return json_unauthorized('Unauthorized')

    company = Company.query.get_or_404(company_id)

    if company.user_id != current_user.id:
        return json_unauthorized('Unauthorized')

    # Remove the link
    note.linked_companies.remove(company)
    db.session.commit()

    return json_success()


@sectors_bp.route('/snippet/<int:snippet_id>/link-companies', methods=['POST'])
@login_required
def link_companies_to_snippet(snippet_id):
    """Link selected companies to a snippet"""
    snippet = SectorResearchSnippet.query.get_or_404(snippet_id)

    # Authorization check
    if snippet.sector_analysis.author != current_user:
        return json_unauthorized('Unauthorized')

    data = request.get_json()
    company_ids = data.get('company_ids', [])

    if not company_ids:
        return json_error('No companies selected')

    # Verify all companies belong to the user
    companies = Company.query.filter(
        Company.id.in_(company_ids),
        Company.user_id == current_user.id
    ).all()

    if len(companies) != len(company_ids):
        return json_error('Invalid company IDs')

    # Clear existing links and add new ones
    # Delete existing associations
    db.session.execute(
        sector_snippet_companies.delete().where(
            sector_snippet_companies.c.sector_snippet_id == snippet_id
        )
    )

    # Add new associations
    for company in companies:
        db.session.execute(
            sector_snippet_companies.insert().values(
                sector_snippet_id=snippet_id,
                company_id=company.id
            )
        )

    db.session.commit()

    return jsonify({
        'success': True,
        'linked_companies': [{
            'id': c.id,
            'name': c.name,
            'ticker': c.ticker_symbol
        } for c in companies]
    })


@sectors_bp.route('/snippet/<int:snippet_id>/unlink-company/<int:company_id>', methods=['POST'])
@login_required
def unlink_company_from_snippet(snippet_id, company_id):
    """Remove a specific company link from a snippet"""
    snippet = SectorResearchSnippet.query.get_or_404(snippet_id)

    # Authorization check
    if snippet.sector_analysis.author != current_user:
        return json_unauthorized('Unauthorized')

    company = Company.query.get_or_404(company_id)

    if company.user_id != current_user.id:
        return json_unauthorized('Unauthorized')

    # Remove the link
    snippet.linked_companies.remove(company)
    db.session.commit()

    return json_success()


# ============================================================================
# TEMPLATE ROUTES
# ============================================================================

@sectors_bp.route('/template/<string:template_key>', methods=['GET'])
@login_required
def get_template_content(template_key):
    """Get template content for insertion into document editor"""
    template = get_template(template_key)

    if not template:
        return json_not_found('Template')

    return jsonify({
        'success': True,
        'content': template['content'],
        'name': template['name'],
        'icon': template['icon']
    })


# ============================================================================
# AI-POWERED FEATURES
# ============================================================================

@sectors_bp.route('/<string:sector_name>/generate-ai-summary', methods=['POST'])
@login_required
def generate_ai_summary(sector_name):
    """
    Generate AI-powered summary of sector research for Key Takeaways.

    Returns JSON with generated summary in HTML format.
    """
    sector = get_sector_by_name_or_slug(sector_name, current_user.id)
    if not sector:
        return json_not_found('Sector')

    analysis = SectorAnalysis.query.filter_by(
        user_id=current_user.id,
        sector_id=sector.id
    ).first_or_404()

    try:
        # Initialize summarization service
        # You can customize the model per use case:
        # - gemini-2.5-flash (default): Fast, cost-effective, good for most tasks
        # - gemini-2.5-pro: More capable, better for complex analysis
        # - gemini-2.0-flash: Alternative fast model
        summarizer = ai_service.summarize(model="gemini-flash-latest")

        # Prepare canvas notes data
        canvas_notes_data = []
        for note in analysis.canvas_notes.all():
            # Strip HTML tags from content for cleaner prompts
            clean_content = re.sub(r'<[^>]+>', '', note.content) if note.content else ''
            canvas_notes_data.append({
                'title': note.title,
                'content': clean_content[:500]  # Limit length
            })

        # Prepare sources data
        sources_data = []
        for source in analysis.sources.all():
            sources_data.append({
                'title': source.title,
                'description': source.description or ''
            })

        # Strip HTML from documentation
        clean_documentation = re.sub(r'<[^>]+>', '', analysis.document_content) if analysis.document_content else ''

        # Get request parameters (optional customization)
        data = request.get_json() or {}
        bullet_count = data.get('bullet_count', 7)
        focus = data.get('focus', 'balanced')  # balanced, insights, risks, opportunities

        # Generate summary
        result = summarizer.generate_sector_summary(
            sector_name=analysis.sector.display_name,
            documentation=clean_documentation,
            canvas_notes=canvas_notes_data,
            sources=sources_data,
            bullet_count=bullet_count,
            focus=focus
        )

        if not result['success']:
            return json_error(result.get('error', 'Failed to generate summary'), status_code=500)

        # Format as HTML for Quill editor
        html_summary = summarizer.format_as_html(result['bullet_points'])

        return jsonify({
            'success': True,
            'summary_html': html_summary,
            'summary_text': result['summary'],
            'bullet_points': result['bullet_points'],
            'token_count': result.get('token_count', 0)
        })

    except Exception as e:
        import traceback
        print(f"Error generating AI summary: {str(e)}")
        print(traceback.format_exc())

        return json_error(f'An error occurred while generating the summary: {str(e)}', status_code=500)