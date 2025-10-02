from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user, login_required
from app import db
from app.models import (SectorAnalysis, QuestionBankItem, SectorResearchSection,
                       Company, ResearchProject, SectorResearchSource)
from sqlalchemy import func
from datetime import datetime
from . import sectors_bp


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

        # Check if an analysis for this sector already exists for the user
        existing = SectorAnalysis.query.filter_by(user_id=current_user.id, sector_name=sector_name.strip()).first()
        if existing:
            flash(f'You already have a research notebook for the "{sector_name}" sector.', 'info')
            # Redirect to the existing notebook page (we'll create this route next)
            return redirect(url_for('sectors.notebook', sector_name=existing.sector_name))

        new_analysis = SectorAnalysis(
            author=current_user,
            sector_name=sector_name.strip()
        )
        db.session.add(new_analysis)
        db.session.commit()

        # Initialize default research sections
        initialize_default_sections(new_analysis)

        flash(f'New research notebook for "{sector_name}" created.', 'success')
        # Redirect to the new notebook page
        return redirect(url_for('sectors.notebook', sector_name=new_analysis.sector_name))


    # GET Request: Fetch and display all existing sector analyses
    sector_analyses = SectorAnalysis.query.filter_by(user_id=current_user.id).order_by(SectorAnalysis.sector_name).all()

    return render_template('list_sectors.html', 
                           title="My Sector Research",
                           sector_analyses=sector_analyses)
    
@sectors_bp.route('/<string:sector_name>', methods=['GET', 'POST'])
@login_required
def notebook(sector_name):
    # Fetch the main analysis object for this sector
    analysis = SectorAnalysis.query.filter_by(user_id=current_user.id, sector_name=sector_name).first_or_404()

    # Initialize sections if they don't exist (backward compatibility for existing analyses)
    if analysis.sections.count() == 0:
        initialize_default_sections(analysis)

    if request.method == 'POST':
        # This POST handles saving the main notes textarea (backward compatible)
        analysis.notes = request.form.get('notes')
        db.session.commit()
        flash('Notes saved successfully.', 'success')
        return redirect(url_for('sectors.notebook', sector_name=analysis.sector_name))

    # GET Request: Fetch questions from the bank that are tagged with this sector
    question_bank_items = QuestionBankItem.query.filter_by(
        user_id=current_user.id,
        sector=sector_name
    ).order_by(QuestionBankItem.created_at.desc()).all()

    # Get all sections ordered by display_order
    sections = analysis.sections.filter_by(is_visible=True).all()

    # Get companies in this sector
    sector_companies = Company.query.filter_by(
        user_id=current_user.id,
        sector=sector_name
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
            Company.sector != sector_name,
            Company.sector.is_(None)
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

    return render_template(
        'sector_analysis.html',
        title=f"Research: {analysis.sector_name}",
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
        sources_by_type=sources_by_type
    )

@sectors_bp.route('/<string:sector_name>/add_question', methods=['POST'])
@login_required
def add_question_to_bank(sector_name):
    # This route specifically handles adding a new question to the bank from the notebook page
    analysis = SectorAnalysis.query.filter_by(user_id=current_user.id, sector_name=sector_name).first_or_404()

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
    if analysis.author != current_user:
        flash("You are not authorized to edit this sector analysis.", "error")
        return redirect(url_for('sectors.index'))

    if request.method == 'POST':
        old_sector_name = analysis.sector_name
        new_sector_name = request.form.get('sector_name', '').strip()

        if not new_sector_name:
            flash("Sector name cannot be empty.", "error")
            return render_template('edit_sector.html', title="Edit Sector", analysis=analysis)

        # Check if a notebook with the new name already exists for this user
        existing = SectorAnalysis.query.filter(
            SectorAnalysis.user_id == current_user.id,
            SectorAnalysis.sector_name == new_sector_name,
            SectorAnalysis.id != analysis.id # Exclude the current one
        ).first()

        if existing:
            flash(f"You already have a research notebook named '{new_sector_name}'.", "error")
            return render_template('edit_sector.html', title="Edit Sector", analysis=analysis)

        # --- Update the Question Bank Items ---
        # Find all questions tagged with the old sector name and update them
        QuestionBankItem.query.filter_by(user_id=current_user.id, sector=old_sector_name)\
                              .update({'sector': new_sector_name})

        # Update the analysis object itself
        analysis.sector_name = new_sector_name

        try:
            db.session.commit()
            flash("Sector analysis updated successfully.", "success")
            # Redirect to the notebook page with the NEW name
            return redirect(url_for('sectors.notebook', sector_name=new_sector_name))
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
    analysis = SectorAnalysis.query.filter_by(user_id=current_user.id, sector_name=sector_name).first_or_404()
    company = Company.query.get_or_404(company_id)

    # Authorization check
    if company.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('sectors.notebook', sector_name=sector_name))

    # Update company sector
    company.sector = sector_name
    db.session.commit()

    flash(f'{company.name} added to {sector_name} sector', 'success')
    return redirect(url_for('sectors.notebook', sector_name=sector_name))


@sectors_bp.route('/<string:sector_name>/remove_company/<int:company_id>', methods=['POST'])
@login_required
def remove_company_from_sector(sector_name, company_id):
    """Remove a company from this sector"""
    analysis = SectorAnalysis.query.filter_by(user_id=current_user.id, sector_name=sector_name).first_or_404()
    company = Company.query.get_or_404(company_id)

    # Authorization check
    if company.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('sectors.notebook', sector_name=sector_name))

    # Clear company sector
    company.sector = None
    db.session.commit()

    flash(f'{company.name} removed from {sector_name} sector', 'success')
    return redirect(url_for('sectors.notebook', sector_name=sector_name))


@sectors_bp.route('/<string:sector_name>/add_source', methods=['POST'])
@login_required
def add_source(sector_name):
    """Add a research source/reference"""
    analysis = SectorAnalysis.query.filter_by(user_id=current_user.id, sector_name=sector_name).first_or_404()

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

    sector_name = source.sector_analysis.sector_name
    db.session.delete(source)
    db.session.commit()

    flash('Source deleted', 'success')
    return redirect(url_for('sectors.notebook', sector_name=sector_name))


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