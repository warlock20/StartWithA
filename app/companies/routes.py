import os
import uuid
import logging
import json


from werkzeug.utils import secure_filename
from datetime import datetime
from sqlalchemy import func
from app.utils.time_utils import parse_date_to_date_object, now_utc
from app.utils.auth_utils import get_user_resource_or_403
from flask import render_template, request, redirect, url_for, flash, current_app, send_from_directory, abort, jsonify, Response, Response
from flask_login import current_user, login_required
from app import db, cache
from app.models import (ResearchProject, Company, CompanyResource, DestinationCheckpoint,
                        ChecklistAnalysis, QualitativeAnalysis,
                        FinancialData, Sector, ResearchLog, ThesisEvolution, DecisionJournal,
                        JournalEntry, LearningNote, MistakeLog, InvestmentPostMortem, IdeaPipeline,
                        Transaction)
from app.models.research import FreeResearchQuestion
from app.services.duplicate_detection import DuplicateDetectionService
from app.services.sector_service import SectorService
from app.services.export_service import export_company_journey, safe_name
from app.companies import companies_bp
from app.celery_tasks import fetch_financial_data_task, fetch_sec_filings_task
from app.utils.ticker_validator import TickerValidator
from app.services.financial_data import FinancialDataService
from app.services.price_service import PriceService
from app.models import PortfolioPosition
from app.services.currency_service import CurrencyService


logger = logging.getLogger(__name__)

# Module-level singleton for financial data lookups
_financial_service = None

def get_financial_service():
    """Lazy initialization of FinancialDataService singleton."""
    global _financial_service
    if _financial_service is None:
        _financial_service = FinancialDataService()
    return _financial_service

# You can define this dictionary at the top of your routes.py file
EXCHANGES = {
    '': 'USA (Default)',
    '.DE': 'Germany (XETRA)',
    '.L': 'United Kingdom (LSE)',
    '.PA': 'France (Euronext Paris)',
    '.T': 'Japan (Tokyo)',
    '.TO': 'Canada (Toronto)',
    '.NS': 'India (NSE)',
    '.HK': 'Hong Kong (HKEX)',
    '.SW': 'Switzerland (SIX)'
    # Add more as needed
}

@cache.memoize(timeout=900)
def get_company_market_data(ticker):
    """
    Fetches market data for a given ticker using FinancialDataService.
    The results of this function will be cached.
    """
    logger.debug(f"Fetching market data for {ticker}")
    try:
        service = get_financial_service()
        info = service.get_ticker_info(ticker)
        if info:
            return {
                'marketCap': info.get('market_cap'),
            }
        return {'marketCap': None}
    except Exception as e:
        logger.warning(f"Market data lookup failed for {ticker}: {e}")
        return {'marketCap': None}

@companies_bp.route('/list')
@login_required
def list_companies():
    """Show all companies with client-side filtering"""
    # Load ALL companies (client-side filtering replaces server-side pagination)
    companies = Company.query.filter_by(user_id=current_user.id).order_by(Company.name).all()

    # Get sets of IDs for categorization
    favorite_ids = {c.id for c in current_user.favorites.all()}
    portfolio_ids = {c.id for c in Company.query.filter_by(user_id=current_user.id, is_in_portfolio=True).all()}

    # Get sets of company IDs that have a specific analysis completed
    completed_checklist_ids = {s.company_id for s in ChecklistAnalysis.query.filter_by(user_id=current_user.id, status='completed').all()}
    swot_analysis_ids = {a.company_id for a in QualitativeAnalysis.query.filter_by(user_id=current_user.id, model_type='SWOT').all()}
    dest_analysis_ids = {c.company_id for c in DestinationCheckpoint.query.filter_by(user_id=current_user.id).all()}

    # Pre-fetch latest research project per company (for richer status)
    all_projects = ResearchProject.query.filter_by(
        user_id=current_user.id
    ).order_by(ResearchProject.created_at.desc()).all()
    latest_project_map = {}
    for p in all_projects:
        if p.company_id not in latest_project_map:
            latest_project_map[p.company_id] = p

    # Batch compute project counts per company (single query instead of N)
    project_counts = dict(
        db.session.query(ResearchProject.company_id, func.count(ResearchProject.id))
        .filter_by(user_id=current_user.id)
        .group_by(ResearchProject.company_id)
        .all()
    )

    # Batch compute resource counts per company (single query instead of N)
    resource_counts = dict(
        db.session.query(CompanyResource.company_id, func.count(CompanyResource.id))
        .filter_by(user_id=current_user.id)
        .group_by(CompanyResource.company_id)
        .all()
    )

    # Pre-compute active projects map from already-loaded projects (no extra query)
    active_projects_map = {}
    for p in all_projects:
        if p.status == 'active' and p.company_id not in active_projects_map:
            active_projects_map[p.company_id] = p

    # Build enriched data for Jinja card view + JSON for Tabulator
    companies_data_list = []
    companies_json_list = []
    for company in companies:
        # Counts from pre-computed maps (no queries)
        project_count = project_counts.get(company.id, 0)
        doc_count = resource_counts.get(company.id, 0)
        active_project = active_projects_map.get(company.id)

        # Derive status from portfolio, favorites, and research project state
        if company.id in portfolio_ids:
            status = 'Portfolio'
        elif company.id in favorite_ids:
            status = 'Watchlist'
        else:
            lp = latest_project_map.get(company.id)
            if lp and lp.status == 'active':
                status = 'Researching'
            elif lp and lp.status == 'completed':
                if lp.decision == 'pass':
                    status = 'Passed'
                elif lp.decision == 'needs_more_work':
                    status = 'Review'
                else:
                    status = 'Tracked'
            elif lp and lp.status == 'killed':
                status = 'Killed'
            else:
                status = 'Tracked'

        # Jinja data (for card view)
        companies_data_list.append({
            'company_obj': company,
            'status': status,
            'has_completed_checklist': company.id in completed_checklist_ids,
            'has_swot': company.id in swot_analysis_ids,
            'has_destination_analysis': company.id in dest_analysis_ids,
            'is_portfolio': company.id in portfolio_ids,
            'is_favorite': company.id in favorite_ids,
        })

        # JSON data (for Tabulator)
        json_entry = {
            'id': company.id,
            'name': company.name,
            'ticker': company.ticker_symbol or '',
            'sector': company.sector.display_name if company.sector else '',
            'status': status,
            'projects': project_count,
            'documents': doc_count,
            'progress': active_project.progress_percentage if active_project else 0,
            'dashboard_url': url_for('companies.company_detail', company_id=company.id),
            'has_destination': company.id in dest_analysis_ids,
            'destination_url': url_for('companies.destination_analysis', company_id=company.id) if company.id in dest_analysis_ids else '',
            'research_url': url_for('research_workflow.project_dashboard', project_id=active_project.id) if active_project else '',
        }
        companies_json_list.append(json_entry)

    # Get all unique sectors for filter dropdown
    all_sectors = db.session.query(Sector.display_name).join(
        Company, Company.sector_id == Sector.id
    ).filter(
        Company.user_id == current_user.id
    ).distinct().order_by(Sector.display_name).all()
    sectors = [s[0] for s in all_sectors]

    return render_template('list_companies.html',
                         companies_data_list=companies_data_list,
                         companies_json=json.dumps(companies_json_list),
                         company_count=len(companies),
                         portfolio_ids=portfolio_ids,
                         favorite_ids=favorite_ids,
                         sectors=sectors,
                         title="All Companies")


@companies_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_company():
    """Add a new company — ticker lookup form, then confirmation."""
    if request.method == 'POST':
        base_ticker = request.form.get('base_ticker', '').strip().upper()
        exchange_suffix = request.form.get('exchange_suffix', '')
        full_ticker = f"{base_ticker}{exchange_suffix}"

        if not base_ticker:
            flash('Please enter a ticker symbol.', 'error')
            return redirect(url_for('companies.new_company'))

        validator = TickerValidator()
        result = validator.validate_ticker(full_ticker)

        if not result.get('valid'):
            flash(f'Could not find company for ticker "{full_ticker}". {result.get("error", "")}', 'error')
            return redirect(url_for('companies.new_company'))

        return render_template('confirm_company.html',
                               name=result.get('name', full_ticker),
                               ticker=full_ticker,
                               summary=result.get('summary', ''),
                               sector=result.get('sector', ''),
                               industry=result.get('industry', ''),
                               title="Confirm Company")

    return render_template('new_company.html',
                           exchanges=EXCHANGES,
                           title="Add New Company")


@companies_bp.route('/add_confirmed', methods=['POST'])
@login_required
def add_company_confirmed():
    for key, value in request.form.items():
        print(f"  - {key}: '{value}'")

    name = request.form.get('name', '').strip() if request.form.get('name') else None
    ticker_symbol = request.form.get('ticker_symbol', '').strip() if request.form.get('ticker_symbol') else None
    summary = request.form.get('summary', '').strip() if request.form.get('summary') else None
    sector = request.form.get('sector', '').strip() if request.form.get('sector') else None
    industry = request.form.get('industry', '').strip() if request.form.get('industry') else None

    # Validate required fields
    if not name or not ticker_symbol:
        flash('Company name and ticker symbol are required.', 'error')
        return redirect(url_for('companies.new_company'))

    # Enhanced duplicate detection
    detector = DuplicateDetectionService(current_user.id)
    duplicate_check = detector.check_company_duplicates(name, ticker_symbol)

    if duplicate_check['is_duplicate']:
        # Handle duplicates with detailed messages
        for match in duplicate_check['exact_matches']:
            flash(match['message'], 'error')
        for match in duplicate_check['similar_matches']:
            if match.get('similarity', 0) > 0.9:  # Very similar names should block
                flash(match['message'], 'error')
        return redirect(url_for('companies.new_company'))

    # Show warnings for similar matches but allow creation
    for match in duplicate_check['similar_matches']:
        if match.get('similarity', 0) <= 0.9:  # Show warning but don't block
            flash(f"Warning: {match['message']}", 'warning')

    if name and ticker_symbol:
        # Find or create sector
        sector_id = None
        if sector:
            sector_obj = SectorService.find_or_create_sector(current_user.id, sector, auto_create=True)
            if sector_obj:
                sector_id = sector_obj.id

        company = Company(name=name, ticker_symbol=ticker_symbol, summary=summary, sector_id=sector_id, industry=industry, creator=current_user)
        company.reporting_currency = CurrencyService.detect_currency_from_ticker(ticker_symbol)
        db.session.add(company)
        db.session.commit()
        flash(f'Company "{name}" ({ticker_symbol}) added successfully!', 'success')
        return redirect(url_for('companies.list_companies'))
    else:
        flash('There was an error adding the company. Please try again.', 'error')
        return redirect(url_for('companies.new_company'))

@companies_bp.route('/<int:company_id>/delete', methods=['POST'])
@login_required
def delete_company(company_id):
    company_to_delete = Company.query.get_or_404(company_id)

    # Authorization check
    if company_to_delete.user_id != current_user.id:
        flash("You are not authorized to delete this company.", "error")
        return redirect(url_for('companies.list_companies'))

    try:
        # Two-phase deletion to handle foreign key constraints
        # Phase 1: Delete related records that reference this company

        # Delete research logs that reference this company
        ResearchLog.query.filter_by(company_id=company_id).delete()

        # Delete thesis evolution entries that reference this company
        ThesisEvolution.query.filter_by(company_id=company_id).delete()

        # Delete decision journal entries that reference this company
        DecisionJournal.query.filter_by(company_id=company_id).delete()

        # Delete journal entries that reference this company
        JournalEntry.query.filter_by(company_id=company_id).delete()

        # Delete learning notes that reference this company
        LearningNote.query.filter_by(company_id=company_id).delete()

        # Delete mistake logs that reference this company
        MistakeLog.query.filter_by(company_id=company_id).delete()

        # Delete investment post-mortems that reference this company
        InvestmentPostMortem.query.filter_by(company_id=company_id).delete()

        # Commit the deletions of related records first
        db.session.commit()

        # Phase 2: Delete the company itself
        # This will now also delete its research sessions, documents, and favorite entries due to cascade settings
        db.session.delete(company_to_delete)
        db.session.commit()

        flash(f'Company "{company_to_delete.name}" and all its data have been deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting company: {str(e)}', 'error')

    return redirect(url_for('companies.list_companies'))


def _gather_journey_data(company, user_id):
    """Gather all journey/timeline data for the unified company page."""
    # Determine company state
    favorite_ids = {c.id for c in current_user.favorites.all()}
    if company.is_in_portfolio:
        company_state = 'portfolio'
    elif company.id in favorite_ids:
        company_state = 'watchlist'
    else:
        company_state = 'new'

    # Get portfolio position (may be None)
    position = PortfolioPosition.query.filter_by(
        user_id=user_id,
        company_id=company.id
    ).first()

    # Get all thesis versions
    thesis_versions = ThesisEvolution.query.filter_by(
        company_id=company.id,
        user_id=user_id
    ).order_by(ThesisEvolution.created_at).all()

    # Get all destination checkpoints
    checkpoints = DestinationCheckpoint.query.filter_by(
        company_id=company.id,
        user_id=user_id
    ).order_by(DestinationCheckpoint.target_date).all()

    # Get transactions (only if portfolio)
    transactions = []
    if company_state == 'portfolio':
        transactions = Transaction.query.filter_by(
            company_id=company.id,
            user_id=user_id
        ).order_by(Transaction.date).all()

    # Get ALL decision journals
    decision_journals = DecisionJournal.query.filter_by(
        company_id=company.id,
        user_id=user_id
    ).order_by(DecisionJournal.decision_date).all()

    # Build unified timeline
    timeline_events = []

    for thesis in thesis_versions:
        timeline_events.append({
            'type': 'thesis',
            'date': thesis.created_at.date() if thesis.created_at else now_utc().date(),
            'datetime': thesis.created_at,
            'data': thesis
        })

    for checkpoint in checkpoints:
        timeline_events.append({
            'type': 'checkpoint',
            'date': checkpoint.target_date,
            'datetime': datetime.combine(checkpoint.target_date, datetime.min.time()),
            'data': checkpoint
        })

    for txn in transactions:
        if txn.type in ['BUY', 'SELL']:
            timeline_events.append({
                'type': 'transaction',
                'date': txn.date,
                'datetime': datetime.combine(txn.date, datetime.min.time()),
                'data': txn
            })

    for decision in decision_journals:
        timeline_events.append({
            'type': 'decision',
            'date': decision.decision_date,
            'datetime': datetime.combine(decision.decision_date, datetime.min.time()),
            'data': decision
        })

    # Research findings
    research_project = ResearchProject.query.filter_by(
        user_id=user_id,
        company_id=company.id
    ).first()

    findings_count = 0
    if research_project:
        for flag in (research_project.green_flags or []):
            timeline_events.append({
                'type': 'finding',
                'date': research_project.created_at.date() if research_project.created_at else now_utc().date(),
                'datetime': research_project.created_at or now_utc(),
                'data': {'text': flag, 'flag_type': 'green'}
            })
        for flag in (research_project.red_flags or []):
            timeline_events.append({
                'type': 'finding',
                'date': research_project.created_at.date() if research_project.created_at else now_utc().date(),
                'datetime': research_project.created_at or now_utc(),
                'data': {'text': flag, 'flag_type': 'red'}
            })
        findings_count = len(research_project.green_flags or []) + len(research_project.red_flags or [])

    # Sort timeline by datetime (most recent first)
    timeline_events.sort(key=lambda x: x['datetime'], reverse=True)

    # Journal entries count (loaded via AJAX)
    journal_entries_count = JournalEntry.query.filter_by(
        user_id=user_id,
        company_id=company.id
    ).count()

    # Journey statistics
    total_return = 0
    days_held = 0
    if position:
        if position.unrealized_gain_loss_pct:
            total_return = position.unrealized_gain_loss_pct
        if position.days_held:
            days_held = position.days_held

    checkpoints_met = sum(1 for cp in checkpoints if cp.status == 'Met')

    current_conviction = 0
    if thesis_versions:
        latest_thesis = max(thesis_versions, key=lambda x: x.created_at or datetime.min)
        current_conviction = latest_thesis.conviction_level or 0

    journey_stats = {
        'total_return': total_return,
        'thesis_updates': len(thesis_versions),
        'checkpoints_met': checkpoints_met,
        'total_checkpoints': len(checkpoints),
        'days_held': days_held,
        'current_conviction': current_conviction,
        'notes_count': journal_entries_count
    }

    # Identify current thesis
    current_thesis = None
    if thesis_versions:
        current_thesis_objs = [t for t in thesis_versions if t.is_current]
        if current_thesis_objs:
            current_thesis = current_thesis_objs[0]
        else:
            current_thesis = max(thesis_versions, key=lambda x: x.created_at or datetime.min)

    # Research tab data: project-linked questions
    free_research_questions = []
    if research_project:
        free_research_questions = FreeResearchQuestion.query.filter_by(
            project_id=research_project.id
        ).order_by(FreeResearchQuestion.created_at).all()

    # Standalone research questions (no project, loaded for initial empty-state check)
    standalone_research_questions = FreeResearchQuestion.query.filter_by(
        company_id=company.id,
        user_id=user_id,
        project_id=None
    ).order_by(FreeResearchQuestion.order_index).all()

    # Portfolio-specific: decision journal and price staleness
    portfolio_decision_journal = None
    price_stale = False
    if company_state == 'portfolio':
        portfolio_decision_journal = DecisionJournal.query.filter_by(
            user_id=user_id,
            company_id=company.id,
            is_portfolio_decision=True
        ).first()
        if position:
            price_stale = PriceService.should_update_price(position)

    return {
        'company_state': company_state,
        'position': position,
        'timeline_events': timeline_events,
        'journey_stats': journey_stats,
        'current_thesis': current_thesis,
        'thesis_count': len(thesis_versions),
        'checkpoint_count': len(checkpoints),
        'transaction_count': len(transactions),
        'decision_count': len(decision_journals),
        'findings_count': findings_count,
        'journal_entries_count': journal_entries_count,
        'research_project': research_project,
        'free_research_questions': free_research_questions,
        'standalone_research_questions': standalone_research_questions,
        'transactions': transactions,
        'portfolio_decision_journal': portfolio_decision_journal,
        'price_stale': price_stale,
    }


def _format_intrinsic_value(company):
    """Format intrinsic value for display with appropriate unit."""
    intrinsic_display_value = ''
    intrinsic_unit = 1
    if company.intrinsic_value:
        val = company.intrinsic_value
        if val >= 1_000_000_000_000:
            intrinsic_unit = 1_000_000_000_000
            intrinsic_display_value = f"{val / intrinsic_unit:.2f}"
        elif val >= 1_000_000_000:
            intrinsic_unit = 1_000_000_000
            intrinsic_display_value = f"{val / intrinsic_unit:.2f}"
        elif val >= 1_000_000:
            intrinsic_unit = 1_000_000
            intrinsic_display_value = f"{val / intrinsic_unit:.2f}"
        else:
            intrinsic_display_value = str(val)
    return intrinsic_display_value, intrinsic_unit


def _format_intrinsic_value_label(company):
    """Format intrinsic value as a human-readable label like '$1.2T' or '$890M'."""
    if not company.intrinsic_value:
        return '—'
    val = company.intrinsic_value
    if val >= 1_000_000_000_000:
        return f"{val / 1_000_000_000_000:.1f}T"
    elif val >= 1_000_000_000:
        return f"{val / 1_000_000_000:.1f}B"
    elif val >= 1_000_000:
        return f"{val / 1_000_000:.1f}M"
    elif val >= 1_000:
        return f"{val / 1_000:.1f}K"
    else:
        return str(val)


@companies_bp.route('/<int:company_id>')
@login_required
def company_detail(company_id):
    """Unified company page — merges dashboard + journey into one."""
    company = get_user_resource_or_403(Company, company_id, current_user.id)

    # Journey data (timeline, thesis, position, stats, research)
    journey_data = _gather_journey_data(company, current_user.id)

    # Ensure current price is converted to user's base currency
    position = journey_data.get('position')
    if position and not position.current_price_base:
        PriceService.update_position_price(position, force=True)

    # Dashboard data: competitors
    current_competitors = company.competitors.order_by(Company.name).all()
    current_competitor_ids = {c.id for c in current_competitors}
    potential_competitors = Company.query.filter(
        Company.user_id == current_user.id,
        Company.id != company_id,
        ~Company.id.in_(current_competitor_ids)
    ).order_by(Company.name).all()

    # Dashboard data: intrinsic value formatting
    intrinsic_display_value, intrinsic_unit = _format_intrinsic_value(company)
    intrinsic_value_label = _format_intrinsic_value_label(company)

    # Dashboard data: currency
    user_currency = current_user.base_currency
    currency_symbol = CurrencyService.get_currency_symbol(user_currency)

    # Resource count for Quick Actions
    resource_count = CompanyResource.query.filter_by(
        company_id=company_id, user_id=current_user.id
    ).count()

    # User's sectors for the settings dropdown
    user_sectors = SectorService.get_user_sectors_list(current_user.id)

    return render_template(
        'company_detail.html',
        company=company,
        # Dashboard data
        intrinsic_display_value=intrinsic_display_value,
        intrinsic_unit=intrinsic_unit,
        intrinsic_value_label=intrinsic_value_label,
        current_competitors=current_competitors,
        potential_competitors=potential_competitors,
        user_currency=user_currency,
        currency_symbol=currency_symbol,
        resource_count=resource_count,
        user_sectors=user_sectors,
        # Journey data
        company_state=journey_data['company_state'],
        position=journey_data['position'],
        timeline_events=journey_data['timeline_events'],
        journey_stats=journey_data['journey_stats'],
        current_thesis=journey_data['current_thesis'],
        thesis_count=journey_data['thesis_count'],
        checkpoint_count=journey_data['checkpoint_count'],
        transaction_count=journey_data['transaction_count'],
        decision_count=journey_data['decision_count'],
        findings_count=journey_data['findings_count'],
        journal_entries_count=journey_data['journal_entries_count'],
        research_project=journey_data['research_project'],
        free_research_questions=journey_data['free_research_questions'],
        standalone_research_questions=journey_data['standalone_research_questions'],
        # Position / transactions data
        transactions=journey_data['transactions'],
        portfolio_decision_journal=journey_data['portfolio_decision_journal'],
        price_stale=journey_data['price_stale'],
        title=f"{company.name}"
    )


@companies_bp.route('/<int:company_id>/toggle_favorite', methods=['POST'])
@login_required
def toggle_favorite(company_id):
    company = Company.query.get_or_404(company_id)
    # Authorization: Ensure user can only favorite their own companies
    if company.user_id != current_user.id:
        flash("You are not authorized to modify this company's favorite status.", "error")
        return redirect(url_for('companies.list_companies'))

    if company in current_user.favorites:
        # If it's already a favorite, remove it
        current_user.favorites.remove(company)
        flash(f'"{company.name}" removed from your favorites.', 'info')
    else:
        # If it's not a favorite, add it
        current_user.favorites.append(company)
        flash(f'"{company.name}" added to your favorites!', 'success')

    db.session.commit()
    # Redirect back to the page the user was on
    return redirect(request.referrer or url_for('companies.list_companies'))

@companies_bp.route('/<int:company_id>/set_intrinsic_value', methods=['POST'])
@login_required
def set_intrinsic_value(company_id):
    company = Company.query.get_or_404(company_id)
    if company.user_id != current_user.id:
        flash("You are not authorized to modify this company.", "error")
        return redirect(url_for('companies.list_companies'))

    value_str = request.form.get('value', '').replace(',', '')
    multiplier_str = request.form.get('unit_multiplier', '1')

    try:
        if value_str:
            value_float = float(value_str)
            multiplier_int = int(multiplier_str)
            # Calculate the final large number
            final_intrinsic_value = int(value_float * multiplier_int)
            company.intrinsic_value = final_intrinsic_value
        else:
            company.intrinsic_value = None # Clear the value if input is empty

        db.session.commit()
        flash("Intrinsic value updated successfully.", "success")
    except (ValueError, TypeError):
        flash("Invalid number format for intrinsic value.", "error")
    except Exception as e:
        db.session.rollback()
        flash(f"An error occurred: {e}", "error")

    return redirect(request.referrer or url_for('companies.company_detail', company_id=company.id))

@companies_bp.route('/<int:company_id>/fetch_sec_filings', methods=['POST'])
@login_required
def fetch_sec_filings(company_id):
    try:
        company = Company.query.get_or_404(company_id)
        if company.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'You are not authorized to perform this action.'}), 403

        data = request.get_json(silent=True) or {}
        filing_type = data.get('filing_type', '10-K')
        years = data.get('years', 5)

        task = fetch_sec_filings_task.delay(company.id, current_user.id, years)

        return jsonify({
            'success': True,
            'task_id': task.id,
            'message': f'{years} year(s) of {filing_type} filings being fetched in the background'
        })
    except Exception as e:
        current_app.logger.error(f"Error starting SEC filings fetch task: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Failed to start task: {str(e)}'
        }), 500
    
@companies_bp.route('/<int:company_id>/toggle_portfolio', methods=['POST'])
@login_required
def toggle_portfolio(company_id):
    """
    DEPRECATED: Old portfolio toggle route.
    Now redirects to transaction system for proper tracking.

    The new portfolio system requires actual transactions (BUY/SELL)
    to track shares, cost basis, and gains/losses properly.
    """
    company = Company.query.get_or_404(company_id)

    # Authorization check
    if company.user_id != current_user.id:
        flash("You are not authorized to modify this company.", "error")
        return redirect(url_for('companies.list_companies'))

    # Check if already in portfolio (has active position)
    position = PortfolioPosition.query.filter_by(
        user_id=current_user.id,
        company_id=company_id,
        is_active=True
    ).first()

    if position:
        # Already in portfolio - suggest selling
        flash(f'"{company.name}" is already in your portfolio with {position.total_shares} shares. To remove, add a SELL transaction.', 'info')
        return redirect(url_for('companies.company_detail', company_id=company_id))
    else:
        # Not in portfolio - redirect to add transaction
        flash(f'To add "{company.name}" to your portfolio, please record a BUY transaction.', 'info')
        return redirect(url_for('portfolio.add_transaction') + f'?company_id={company_id}')
 

@companies_bp.route('/<int:company_id>/swot', methods=['GET', 'POST'])
@login_required
def swot_analysis(company_id):
    company = Company.query.get_or_404(company_id)
    # Authorization check
    if company.user_id != current_user.id:
        flash("You are not authorized to access this page.", "error")
        return redirect(url_for('companies.list_companies'))

    # Try to find an existing SWOT analysis for this company and user
    analysis = QualitativeAnalysis.query.filter_by(
        user_id=current_user.id,
        company_id=company.id,
        model_type='SWOT'
    ).first()

    if request.method == 'POST':
        # Get content from the four text areas
        strengths = request.form.get('strengths', '')
        weaknesses = request.form.get('weaknesses', '')
        opportunities = request.form.get('opportunities', '')
        threats = request.form.get('threats', '')

        # Store the content in a dictionary (JSON)
        content_data = {
            'strengths': strengths,
            'weaknesses': weaknesses,
            'opportunities': opportunities,
            'threats': threats
        }

        if analysis:
            # If analysis already exists, update its content
            analysis.content = content_data
        else:
            # If no analysis exists, create a new one
            analysis = QualitativeAnalysis(
                user_id=current_user.id,
                company_id=company.id,
                model_type='SWOT',
                content=content_data
            )
            db.session.add(analysis)

        try:
            db.session.commit()
            flash('SWOT analysis saved successfully.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred while saving: {e}', 'error')

        # Preserve research workflow context if present
        project_id = request.args.get('project_id')
        step_index = request.args.get('step_index')
        if project_id and step_index:
            return redirect(url_for('companies.swot_analysis',
                                  company_id=company.id,
                                  project_id=project_id,
                                  step_index=step_index))
        else:
            return redirect(url_for('companies.swot_analysis', company_id=company.id))

    # For a GET request, prepare the existing data for the form
    existing_content = analysis.content if analysis and analysis.content else {}

    return render_template(
        'swot_analysis.html',
        title=f"SWOT Analysis for {company.name}",
        company=company,
        analysis_content=existing_content # Pass the content dictionary to the template
    )
    
@companies_bp.route('/<int:company_id>/fetch_financials', methods=['POST'])
@login_required
def fetch_financials(company_id):
    try:
        company = Company.query.get_or_404(company_id)
        if company.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'You are not authorized to perform this action.'}), 403

        # Call the background task, passing only the company ID
        task = fetch_financial_data_task.delay(company.id)

        # Return JSON response with task ID for polling
        return jsonify({
            'success': True,
            'task_id': task.id,
            'message': 'Financial data fetch started in background'
        })
    except Exception as e:
        current_app.logger.error(f"Error starting financial fetch task: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Failed to start task: {str(e)}'
        }), 500
 
@companies_bp.route('/<int:company_id>/financials')
@login_required
def financials(company_id):
    company = Company.query.get_or_404(company_id)
    if company.user_id != current_user.id:
        flash("You are not authorized to access this page.", "error")
        return redirect(url_for('companies.list_companies'))

    # Fetch all financial data for this company, ordered by date
    all_financial_data = company.financial_data.order_by(FinancialData.period_date.asc()).all()

    # --- Prepare data for charts ---
    # We need to pivot the data from our "long" database format to a "wide" format for charting.

    chart_data = {
        'revenue': {'labels': [], 'values': []},
        'net_income': {'labels': [], 'values': []}
    }

    for data_point in all_financial_data:
        year = data_point.period_date.strftime('%Y')
        if data_point.metric_name == 'Total Revenue':
            if year not in chart_data['revenue']['labels']: # Avoid duplicate years if data is quarterly
                chart_data['revenue']['labels'].append(year)
                chart_data['revenue']['values'].append(data_point.value)
        elif data_point.metric_name == 'Net Income':
            if year not in chart_data['net_income']['labels']:
                chart_data['net_income']['labels'].append(year)
                chart_data['net_income']['values'].append(data_point.value)

    return render_template(
        'financials.html',
        title=f"Financials for {company.name}",
        company=company,
        chart_data=chart_data # Pass the prepared data to the template
    )

@companies_bp.route('/<int:company_id>/add_competitor', methods=['POST'])
@login_required
def add_competitor(company_id):
    company = get_user_resource_or_403(Company, company_id, current_user.id)

    competitor_id = request.form.get('competitor_id', type=int)
    if not competitor_id:
        flash('No competitor selected.', 'error')
        return redirect(url_for('companies.company_detail', company_id=company_id))

    competitor = get_user_resource_or_403(Company, competitor_id, current_user.id)

    if competitor in company.competitors:
        flash(f'"{competitor.name}" is already a competitor.', 'warning')
    else:
        company.competitors.append(competitor)
        db.session.commit()
        flash(f'"{competitor.name}" added as a competitor.', 'success')

    return redirect(url_for('companies.company_detail', company_id=company_id))

@companies_bp.route('/<int:company_id>/remove_competitor/<int:competitor_id>', methods=['POST'])
@login_required
def remove_competitor(company_id, competitor_id):
    company = get_user_resource_or_403(Company, company_id, current_user.id)

    competitor = Company.query.get_or_404(competitor_id)
    if competitor in company.competitors:
        company.competitors.remove(competitor)
        db.session.commit()
        flash(f'"{competitor.name}" removed from competitors.', 'info')

    return redirect(url_for('companies.company_detail', company_id=company_id))

@companies_bp.route('/<int:company_id>/edit', methods=['POST'])
@login_required
def edit_company(company_id):
    """Update company details including ticker symbol, name, sector, and industry"""
    company = Company.query.get_or_404(company_id)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    # Authorization check
    if company.user_id != current_user.id:
        if is_ajax:
            return jsonify({'success': False, 'error': 'Not authorized'}), 403
        flash("You are not authorized to edit this company.", "error")
        return redirect(url_for('companies.list_companies'))

    # Get form data
    name = request.form.get('name', '').strip()
    ticker_symbol = request.form.get('ticker_symbol', '').strip().upper()
    summary = request.form.get('summary', '').strip()
    sector_name = request.form.get('sector', '').strip()
    industry = request.form.get('industry', '').strip()

    # Validate required fields
    if not name or not ticker_symbol:
        if is_ajax:
            return jsonify({'success': False, 'error': 'Company name and ticker symbol are required.'}), 400
        flash('Company name and ticker symbol are required.', 'error')
        return redirect(url_for('companies.company_detail', company_id=company_id))

    # Check if ticker is changing and validate it
    ticker_changed = (ticker_symbol != company.ticker_symbol)
    new_currency = None
    if ticker_changed:
        # Validate ticker with Yahoo Finance
        validator = TickerValidator()
        validation_result = validator.validate_ticker(ticker_symbol)

        if not validation_result['valid']:
            msg = f'Invalid ticker symbol: {validation_result.get("error", "Could not validate ticker")}'
            if is_ajax:
                return jsonify({'success': False, 'error': msg}), 400
            flash(msg, 'error')
            return redirect(url_for('companies.company_detail', company_id=company_id))

        # Detect the new ticker's currency
        new_currency = validation_result.get('currency')
        if not new_currency:
            new_currency = CurrencyService.detect_currency_from_ticker(ticker_symbol)

        # Check for duplicate ticker in user's companies
        existing_company = Company.query.filter_by(
            user_id=current_user.id,
            ticker_symbol=ticker_symbol
        ).filter(Company.id != company_id).first()

        if existing_company:
            msg = f'You already have a company with ticker "{ticker_symbol}": {existing_company.name}'
            if is_ajax:
                return jsonify({'success': False, 'error': msg}), 400
            flash(msg, 'error')
            return redirect(url_for('companies.company_detail', company_id=company_id))

    # Update company fields
    old_name = company.name
    old_ticker = company.ticker_symbol

    company.name = name
    company.ticker_symbol = ticker_symbol
    company.summary = summary if summary else None
    company.industry = industry if industry else None

    # Update reporting currency when ticker changes
    if ticker_changed and new_currency:
        company.reporting_currency = new_currency

    # Handle sector
    if sector_name and sector_name != '__new__':
        sector_obj = SectorService.find_or_create_sector(current_user.id, sector_name, auto_create=True)
        if sector_obj:
            company.sector_id = sector_obj.id
    else:
        company.sector_id = None

    try:
        db.session.commit()

        # Build success message with changes summary
        changes = []
        if old_name != name:
            changes.append(f'name updated to "{name}"')
        if old_ticker != ticker_symbol:
            changes.append(f'ticker updated to "{ticker_symbol}"')
            # If ticker changed and company is in portfolio, force price update
            if company.is_in_portfolio:
                positions = PortfolioPosition.query.filter_by(
                    user_id=current_user.id,
                    company_id=company_id,
                    is_active=True
                ).all()

                for position in positions:
                    PriceService.update_position_price(position, force=True)

                if not is_ajax:
                    flash('Portfolio positions updated with new ticker symbol.', 'info')

        if is_ajax:
            msg = f'Company updated: {", ".join(changes)}' if changes else 'Company details saved.'
            return jsonify({
                'success': True,
                'message': msg,
                'name': company.name,
                'ticker_symbol': company.ticker_symbol,
                'sector_name': (company.sector.display_name or company.sector.name) if company.sector else None
            })

        if changes:
            flash(f'Company updated successfully: {", ".join(changes)}', 'success')
        else:
            flash('Company details saved.', 'success')

    except Exception as e:
        db.session.rollback()
        if is_ajax:
            return jsonify({'success': False, 'error': f'Error updating company: {str(e)}'}), 500
        flash(f'Error updating company: {str(e)}', 'error')

    return redirect(url_for('companies.company_detail', company_id=company_id))

@companies_bp.route('/validate_ticker', methods=['POST'])
@login_required
def validate_ticker_api():
    """API endpoint for real-time ticker validation"""
    data = request.get_json()
    ticker = data.get('ticker', '').strip().upper()

    if not ticker:
        return jsonify({
            'valid': False,
            'error': 'Ticker symbol is required'
        }), 400

    validator = TickerValidator()
    result = validator.validate_ticker(ticker)

    return jsonify(result)


@companies_bp.route('/<int:company_id>/journey/export', methods=['POST'])
@login_required
def export_company_journey_route(company_id):
    """Export selected company journey components as a ZIP archive."""
    company = Company.query.filter_by(
        id=company_id, user_id=current_user.id
    ).first_or_404()

    # Determine company state (same logic as company_journey route)
    favorite_ids = {c.id for c in current_user.favorites.all()}
    if company.is_in_portfolio:
        company_state = 'portfolio'
    elif company.id in favorite_ids:
        company_state = 'watchlist'
    else:
        company_state = 'new'

    # Get selected components from form checkboxes
    all_components = ['thesis', 'checkpoints', 'transactions', 'decisions',
                      'journal', 'notes', 'research']
    selected = [c for c in all_components if request.form.get(f'export_{c}')]

    if not selected:
        flash('Please select at least one component to export.', 'warning')
        return redirect(url_for('companies.company_detail', company_id=company_id))

    # Guard: transactions only for portfolio companies
    if 'transactions' in selected and company_state != 'portfolio':
        selected.remove('transactions')

    zip_bytes = export_company_journey(
        company=company,
        user_id=current_user.id,
        components=selected,
        company_state=company_state
    )

    company_name = safe_name(company.name)
    date_str = now_utc().strftime('%Y-%m-%d')
    zip_filename = f"{company_name}_Journey_{date_str}.zip"

    return Response(
        zip_bytes,
        mimetype='application/zip',
        headers={'Content-Disposition': f'attachment; filename="{zip_filename}"'}
    )
