from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user, login_required
from app import db
from app.models import (SectorAnalysis, QuestionBankItem, SectorResearchSection,
                       Company, ResearchProject, SectorResearchSource, SectorResearchSnippet,
                       SectorSection, SectorNote)
from app.models.associations import sector_note_companies, sector_snippet_companies
from app.services.sector_service import SectorService
from app.services.too_hard_service import TooHardBasketService
from sqlalchemy import func
from datetime import datetime
import re
from . import sectors_bp
from .research_templates import get_all_templates, get_template_list, get_template
from app.ai import SummarizationService


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
    from app.models.sector import Sector as SectorModel

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
            'title': 'Industry Analysis (Porter\'s 5 Forces)',
            'icon': '🔍',
            'description': 'Analyze competitive rivalry, barriers to entry, supplier/buyer power, and threat of substitutes',
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
        from app.models.sector import Sector as SectorModel
        from app.services.sector_service import SectorService
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
    
@sectors_bp.route('/<string:sector_name>', methods=['GET', 'POST'])
@login_required
def notebook(sector_name):
    # Look up the Sector object with canonicalization check
    sector, should_redirect = get_sector_by_name_or_slug(sector_name, current_user.id, redirect_to_canonical=True)

    if not sector:
        flash('Sector not found', 'error')
        return redirect(url_for('sectors.list_sectors'))

    # Redirect to canonical slug URL if accessed via display_name
    if should_redirect:
        return redirect(url_for('sectors.notebook', sector_name=sector.slug), code=301)

    # Fetch the main analysis object for this sector
    analysis = SectorAnalysis.query.filter_by(user_id=current_user.id, sector_id=sector.id).first_or_404()

    # Initialize sections if they don't exist (backward compatibility for existing analyses)
    if analysis.sections.count() == 0:
        initialize_default_sections(analysis)

    if request.method == 'POST':
        # This shouldn't be used anymore - atomic notes and document view handle saving
        flash('Please use the Document View or Research Canvas to save your notes.', 'info')
        return redirect(url_for('sectors.notebook', sector_name=sector.slug))

    # GET Request: Fetch questions from the bank that are tagged with this sector
    question_bank_items = QuestionBankItem.query.filter_by(
        user_id=current_user.id,
        sector_id=sector.id
    ).order_by(QuestionBankItem.created_at.desc()).all()

    # Get all sections ordered by display_order
    sections = analysis.sections.filter_by(is_visible=True).all()

    # Get companies in this sector
    sector_companies = Company.query.filter_by(
        user_id=current_user.id,
        sector_id=sector.id
    ).all()

    # Enrich with research project status
    companies_data = []
    for company in sector_companies:
        # Get active research project
        active_project = ResearchProject.query.filter_by(
            user_id=current_user.id,
            company_id=company.id,
            status='active'
        ).first()

        # Get completed research project
        completed_project = ResearchProject.query.filter_by(
            user_id=current_user.id,
            company_id=company.id,
            status='completed'
        ).first()

        companies_data.append({
            'company': company,
            'active_project': active_project,
            'completed_project': completed_project,
            'is_in_watchlist': company in current_user.favorites.all(),
            'is_in_portfolio': company.is_in_portfolio
        })

    # Get all user companies not in this sector (for adding)
    other_companies = Company.query.filter(
        Company.user_id == current_user.id,
        db.or_(
            Company.sector_id != sector.id,
            Company.sector_id.is_(None)
        )
    ).order_by(Company.name).all()

    # Calculate sector metrics
    total_companies = len(sector_companies)
    researched_companies = sum(1 for c in companies_data if c['completed_project'])
    watchlist_companies = sum(1 for c in companies_data if c['is_in_watchlist'])
    portfolio_companies = sum(1 for c in companies_data if c['is_in_portfolio'])

    # Get research sources
    sources = analysis.sources.order_by(SectorResearchSource.created_at.desc()).all()

    # Group sources by type
    sources_by_type = {}
    for source in sources:
        source_type = source.source_type
        if source_type not in sources_by_type:
            sources_by_type[source_type] = []
        sources_by_type[source_type].append(source)

    # Get research snippets
    snippets = analysis.snippets.order_by(SectorResearchSnippet.created_at.desc()).all()

    # Group snippets by category
    snippets_by_category = {}
    for snippet in snippets:
        category = snippet.category
        if category not in snippets_by_category:
            snippets_by_category[category] = []
        snippets_by_category[category].append(snippet)

    # Get canvas sections and notes
    canvas_sections = analysis.canvas_sections.order_by(SectorSection.sort_order).all()

    # Get unorganized notes (collector items)
    collector_notes = analysis.canvas_notes.filter(SectorNote.section_id == None).order_by(SectorNote.created_at.desc()).all()

    # Get sector analytics and passed companies
    sector_stats = SectorService.get_sector_stats(sector.id, current_user.id) if sector else None

    # Get passed companies for this sector from Too Hard Basket
    passed_companies_data = []
    if sector:
        all_too_hard = TooHardBasketService.get_all_too_hard_companies(current_user.id, {})
        # Filter to only this sector
        sector_passed = [item for item in all_too_hard if item.sector == sector.display_name]

        for item in sector_passed:
            passed_companies_data.append({
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
            })

    return render_template(
        'sector_analysis.html',
        title=f"Research: {analysis.sector.display_name}",
        analysis=analysis,
        question_bank_items=question_bank_items,
        sections=sections,
        companies_data=companies_data,
        other_companies=other_companies,
        sector_metrics={
            'total': total_companies,
            'researched': researched_companies,
            'watchlist': watchlist_companies,
            'portfolio': portfolio_companies
        },
        sources=sources,
        sources_by_type=sources_by_type,
        snippets=snippets,
        snippets_by_category=snippets_by_category,
        canvas_sections=canvas_sections,
        collector_notes=collector_notes,
        research_templates=get_all_templates(),
        template_list=get_template_list(),
        sector_stats=sector_stats,
        passed_companies=passed_companies_data
    )

@sectors_bp.route('/<string:sector_name>/add_question', methods=['POST'])
@login_required
def add_question_to_bank(sector_name):
    # This route specifically handles adding a new question to the bank from the notebook page
    sector = get_sector_by_name_or_slug(sector_name, current_user.id)
    if not sector:
        flash('Sector not found', 'error')
        return redirect(url_for('sectors.index'))

    analysis = SectorAnalysis.query.filter_by(user_id=current_user.id, sector_id=sector.id).first_or_404()

    text = request.form.get('text')
    llm_prompt = request.form.get('llm_prompt')

    if not text:
        flash('Question text is required.', 'error')
    else:
        new_question = QuestionBankItem(
            author=current_user,
            text=text,
            llm_prompt=llm_prompt if llm_prompt else None,
            sector=sector_name # Automatically tag with the current sector
        )
        db.session.add(new_question)
        db.session.commit()
        flash('New question added to your bank for this sector.', 'success')

    return redirect(url_for('sectors.notebook', sector_name=sector_name))

@sectors_bp.route('/question_bank_item/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_question_from_bank(item_id):
    # This route handles deleting a question and redirects back to the notebook page
    question = QuestionBankItem.query.get_or_404(item_id)
    if question.author != current_user:
        flash('You are not authorized to delete this item.', 'error')
        return redirect(url_for('sectors.index'))

    sector_name = question.sector # Get sector name for redirect before deleting
    db.session.delete(question)
    db.session.commit()
    flash('Question deleted from your bank.', 'success')

    # If we came from a sector page, redirect back there. Otherwise, to the main bank.
    if sector_name:
        return redirect(url_for('sectors.notebook', sector_name=sector_name))
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
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

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
        return jsonify({'success': False, 'error': str(e)}), 500


@sectors_bp.route('/<string:sector_name>/add_company/<int:company_id>', methods=['POST'])
@login_required
def add_company_to_sector(sector_name, company_id):
    """Add a company to this sector"""
    sector = get_sector_by_name_or_slug(sector_name, current_user.id)
    if not sector:
        flash('Sector not found', 'error')
        return redirect(url_for('sectors.index'))

    analysis = SectorAnalysis.query.filter_by(user_id=current_user.id, sector_id=sector.id).first_or_404()
    company = Company.query.get_or_404(company_id)

    # Authorization check
    if company.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('sectors.notebook', sector_name=sector_name))

    # Update company sector
    company.sector_id = sector.id
    db.session.commit()

    flash(f'{company.name} added to {sector.display_name} sector', 'success')
    return redirect(url_for('sectors.notebook', sector_name=sector_name))


@sectors_bp.route('/<string:sector_name>/remove_company/<int:company_id>', methods=['POST'])
@login_required
def remove_company_from_sector(sector_name, company_id):
    """Remove a company from this sector"""
    sector = get_sector_by_name_or_slug(sector_name, current_user.id)
    if not sector:
        flash('Sector not found', 'error')
        return redirect(url_for('sectors.index'))

    analysis = SectorAnalysis.query.filter_by(user_id=current_user.id, sector_id=sector.id).first_or_404()
    company = Company.query.get_or_404(company_id)

    # Authorization check
    if company.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('sectors.notebook', sector_name=sector_name))

    # Clear company sector
    company.sector_id = None
    db.session.commit()

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
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    source.accessed_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'success': True})


@sectors_bp.route('/<string:sector_name>/add_snippet', methods=['POST'])
@login_required
def add_snippet(sector_name):
    """Add a research snippet"""
    analysis = SectorAnalysis.query.filter_by(
        user_id=current_user.id,
        sector_name=sector_name
    ).first_or_404()

    data = request.get_json()
    content = data.get('content', '').strip()
    category = data.get('category', '').strip()
    tags = data.get('tags', '').strip()
    notes = data.get('notes', '').strip()

    if not content or not category:
        return jsonify({'success': False, 'error': 'Content and category are required'}), 400

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
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

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
    analysis = SectorAnalysis.query.filter_by(
        user_id=current_user.id,
        sector_name=sector_name
    ).first_or_404()

    data = request.get_json()
    title = data.get('title', '').strip()

    if not title:
        return jsonify({'success': False, 'error': 'Title is required'}), 400

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
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

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

    return jsonify({'success': True})


@sectors_bp.route('/section/<int:section_id>/delete', methods=['POST'])
@login_required
def delete_section(section_id):
    """Delete a section (notes will be moved to collector)"""
    section = SectorSection.query.get_or_404(section_id)

    if section.sector_analysis.author != current_user:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    # Move all notes in this section to collector (set section_id to None)
    SectorNote.query.filter_by(section_id=section_id).update({'section_id': None})

    db.session.delete(section)
    db.session.commit()

    return jsonify({'success': True})


@sectors_bp.route('/<string:sector_name>/note/create', methods=['POST'])
@login_required
def create_note(sector_name):
    """Create a new note"""
    analysis = SectorAnalysis.query.filter_by(
        user_id=current_user.id,
        sector_name=sector_name
    ).first_or_404()

    data = request.get_json()
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()

    if not title or not content:
        return jsonify({'success': False, 'error': 'Title and content are required'}), 400

    section_id = data.get('section_id')

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
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    data = request.get_json()

    if 'title' in data:
        note.title = data['title'].strip()
    if 'content' in data:
        note.content = data['content'].strip()
    if 'section_id' in data:
        note.section_id = data.get('section_id')
    if 'sort_order' in data:
        note.sort_order = data['sort_order']
    if 'tags' in data:
        note.tags = data.get('tags')
    if 'source_reference' in data:
        note.source_reference = data.get('source_reference')
    if 'source_title' in data:
        note.source_title = data.get('source_title')

    db.session.commit()

    return jsonify({'success': True})


@sectors_bp.route('/note/<int:note_id>/delete', methods=['POST'])
@login_required
def delete_note(note_id):
    """Delete a note"""
    note = SectorNote.query.get_or_404(note_id)

    if note.sector_analysis.author != current_user:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    db.session.delete(note)
    db.session.commit()

    return jsonify({'success': True})


@sectors_bp.route('/<string:sector_name>/generate-document', methods=['GET'])
@login_required
def generate_document_from_canvas(sector_name):
    """Generate a formatted document from canvas sections and notes"""
    try:
        analysis = SectorAnalysis.query.filter_by(
            user_id=current_user.id,
            sector_name=sector_name
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

        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500


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
        return jsonify({'success': False, 'error': 'Sector not found'}), 404

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
        return jsonify({'success': False, 'error': 'Sector not found'}), 404

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

    analysis.updated_at = datetime.utcnow()

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
    analysis.archived_at = datetime.utcnow()
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
        return jsonify({'success': False, 'error': 'No text provided'}), 400

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
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    data = request.get_json()
    company_ids = data.get('company_ids', [])

    if not company_ids:
        return jsonify({'success': False, 'error': 'No companies selected'}), 400

    # Verify all companies belong to the user
    companies = Company.query.filter(
        Company.id.in_(company_ids),
        Company.user_id == current_user.id
    ).all()

    if len(companies) != len(company_ids):
        return jsonify({'success': False, 'error': 'Invalid company IDs'}), 400

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
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    company = Company.query.get_or_404(company_id)

    if company.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    # Remove the link
    note.linked_companies.remove(company)
    db.session.commit()

    return jsonify({'success': True})


@sectors_bp.route('/snippet/<int:snippet_id>/link-companies', methods=['POST'])
@login_required
def link_companies_to_snippet(snippet_id):
    """Link selected companies to a snippet"""
    snippet = SectorResearchSnippet.query.get_or_404(snippet_id)

    # Authorization check
    if snippet.sector_analysis.author != current_user:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    data = request.get_json()
    company_ids = data.get('company_ids', [])

    if not company_ids:
        return jsonify({'success': False, 'error': 'No companies selected'}), 400

    # Verify all companies belong to the user
    companies = Company.query.filter(
        Company.id.in_(company_ids),
        Company.user_id == current_user.id
    ).all()

    if len(companies) != len(company_ids):
        return jsonify({'success': False, 'error': 'Invalid company IDs'}), 400

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
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    company = Company.query.get_or_404(company_id)

    if company.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    # Remove the link
    snippet.linked_companies.remove(company)
    db.session.commit()

    return jsonify({'success': True})


# ============================================================================
# TEMPLATE ROUTES
# ============================================================================

@sectors_bp.route('/template/<string:template_key>', methods=['GET'])
@login_required
def get_template_content(template_key):
    """Get template content for insertion into document editor"""
    template = get_template(template_key)

    if not template:
        return jsonify({'success': False, 'error': 'Template not found'}), 404

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
    analysis = SectorAnalysis.query.filter_by(
        user_id=current_user.id,
        sector_name=sector_name
    ).first_or_404()

    try:
        # Initialize summarization service
        # You can customize the model per use case:
        # - gemini-2.5-flash (default): Fast, cost-effective, good for most tasks
        # - gemini-2.5-pro: More capable, better for complex analysis
        # - gemini-2.0-flash: Alternative fast model
        summarizer = SummarizationService(model="gemini-flash-latest")

        # Prepare canvas notes data
        canvas_notes_data = []
        for note in analysis.canvas_notes.all():
            # Strip HTML tags from content for cleaner prompts
            clean_content = re.sub(r'<[^>]+>', '', note.content) if note.content else ''
            canvas_notes_data.append({
                'title': note.title,
                'content': clean_content[:500]  # Limit length
            })

        # Prepare snippets data
        snippets_data = []
        for snippet in analysis.snippets.all():
            clean_content = re.sub(r'<[^>]+>', '', snippet.content) if snippet.content else ''
            snippets_data.append({
                'content': clean_content[:300],
                'category': snippet.category
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
            snippets=snippets_data,
            sources=sources_data,
            bullet_count=bullet_count,
            focus=focus
        )

        if not result['success']:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Failed to generate summary')
            }), 500

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

        return jsonify({
            'success': False,
            'error': f'An error occurred while generating the summary: {str(e)}'
        }), 500