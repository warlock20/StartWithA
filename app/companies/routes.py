import os
import uuid
import logging
import json


from werkzeug.utils import secure_filename
from datetime import datetime
from itertools import groupby
from flask import render_template, request, redirect, url_for, flash, current_app, send_from_directory, abort, jsonify
from flask_login import current_user, login_required
from app import db, cache
from app.models import (ResearchProject, Company, CompanyDocument, DestinationCheckpoint,
                        ChecklistAnalysis, CompanyArticle, ScuttlebuttAnalysis, QualitativeAnalysis,
                        FinancialData, Sector, ResearchLog, ThesisEvolution, DecisionJournal,
                        JournalEntry, LearningNote, MistakeLog, InvestmentPostMortem, IdeaPipeline)
from app.services.duplicate_detection import DuplicateDetectionService
from app.services.sector_service import SectorService
from app.companies import companies_bp
from app.celery_tasks import fetch_financial_data_task, fetch_sec_filings_task, fetch_company_news_task, analyze_scuttlebutt_task
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

    # Build enriched data for Jinja card view + JSON for Tabulator
    companies_data_list = []
    companies_json_list = []
    for company in companies:
        # Counts for table
        project_count = current_user.research_projects.filter_by(company_id=company.id).count()
        doc_count = company.documents.count()
        active_project = current_user.research_projects.filter_by(company_id=company.id, status='active').first()

        status = 'Portfolio' if company.id in portfolio_ids else ('Watchlist' if company.id in favorite_ids else 'Tracked')

        # Jinja data (for card view)
        companies_data_list.append({
            'company_obj': company,
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
            'dashboard_url': url_for('companies.company_dashboard', company_id=company.id),
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

@companies_bp.route('/<int:company_id>/add_document', methods=['POST'])
@login_required
def add_document(company_id):
    company = Company.query.get_or_404(company_id)
    if company.user_id != current_user.id:
        abort(403)

    # --- Basic File Checks ---
    if 'document_file' not in request.files:
        flash('No file part in request.', 'error')
        return redirect(url_for('companies.company_dashboard', company_id=company_id) + '#documents')

    file = request.files['document_file']
    if file.filename == '':
        flash('No file selected for upload.', 'error')
        return redirect(url_for('companies.company_dashboard', company_id=company_id) + '#documents')

    # --- Get all form data ---
    doc_group = request.form.get('document_group')
    doc_title = request.form.get('document_title')
    doc_date_str = request.form.get('document_date')
    doc_description = request.form.get('description')

    # --- Full Validation and Processing Logic ---
    if not doc_group or not doc_title:
        flash('Document group and title are required.', 'error')
    elif file:
        original_fn = secure_filename(file.filename)
        file_ext = os.path.splitext(original_fn)[1].lower()
        # Ensure ALLOWED_EXTENSIONS is a set, e.g. {'pdf', 'txt'}
        allowed_extensions = current_app.config['ALLOWED_EXTENSIONS']

        if not original_fn.lower().endswith(tuple(f".{ext}" for ext in allowed_extensions)):
            flash(f'File type not allowed. Allowed types are: {", ".join(allowed_extensions)}', 'error')
        else:
            try:
                stored_fn = f"{uuid.uuid4().hex}{file_ext}"
                company_specific_upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], str(company.id))
                os.makedirs(company_specific_upload_path, exist_ok=True)
                file.save(os.path.join(company_specific_upload_path, stored_fn))

                document_date_obj = None
                if doc_date_str:
                    try:
                        document_date_obj = datetime.strptime(doc_date_str, '%Y-%m-%d').date()
                    except ValueError:
                        flash('Invalid date format. Please use YYYY-MM-DD.', 'error')
                        # It might be better to return and not save if date is invalid
                        return redirect(url_for('companies.company_dashboard', company_id=company_id) + '#documents')
                
                new_doc = CompanyDocument(
                    company_id=company.id, 
                    user_id=current_user.id,
                    original_filename=original_fn,
                    stored_filename=os.path.join(str(company.id), stored_fn),
                    document_group=doc_group, 
                    document_title=doc_title,
                    document_date=document_date_obj, 
                    description=doc_description
                )
                db.session.add(new_doc)
                db.session.commit()
                flash(f'Document "{original_fn}" uploaded successfully.', 'success')

            except Exception as e:
                db.session.rollback()
                flash(f"An error occurred during upload: {e}", "error")
                print(f"ERROR: Document upload failed: {e}")

    return redirect(url_for('companies.company_dashboard', company_id=company_id) + '#documents')

@companies_bp.route('/<int:company_id>/documents', methods=['GET']) # This is your dashboard page
@login_required
def company_dashboard(company_id):
    company = Company.query.get_or_404(company_id)
    if company.user_id != current_user.id:
        abort(403)

    # Data for Documents Tab
    documents_query = company.documents.order_by(CompanyDocument.document_group, CompanyDocument.document_date.desc()).all()
    grouped_documents = {group: list(docs) for group, docs in groupby(documents_query, key=lambda doc: doc.document_group)}
    distinct_group_names_query = db.session.query(CompanyDocument.document_group).filter(CompanyDocument.user_id == current_user.id).distinct().order_by(CompanyDocument.document_group).all()
    distinct_group_names = [group[0] for group in distinct_group_names_query if group[0]]

    # Data for Competitors Tab
    current_competitors = company.competitors.order_by(Company.name).all()
    current_competitor_ids = {c.id for c in current_competitors}
    potential_competitors = Company.query.filter(
        Company.user_id == current_user.id,
        Company.id != company_id,
        ~Company.id.in_(current_competitor_ids)
    ).order_by(Company.name).all()

    # Data for Overview Tab (Intrinsic Value form)
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

    # Get user currency settings for display
    user_currency = current_user.base_currency
    currency_symbol = CurrencyService.get_currency_symbol(user_currency)

    return render_template(
        'company_documents.html',
        company=company,
        grouped_documents=grouped_documents,
        distinct_group_names=distinct_group_names,
        intrinsic_display_value=intrinsic_display_value,
        intrinsic_unit=intrinsic_unit,
        current_competitors=current_competitors,
        potential_competitors=potential_competitors,
        user_currency=user_currency,
        currency_symbol=currency_symbol,
        title=f"Dashboard for {company.name}"
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

    return redirect(request.referrer or url_for('companies.company_dashboard', company_id=company.id))

@companies_bp.route('/documents/serve/<path:filepath>') # /companies/documents/serve/<company_id>/<filename>
@login_required
def serve_company_document(filepath):
    # filepath is expected to be "<company_id>/<stored_filename>"
    try:
        # Basic security: Ensure the filepath is not attempting to traverse upwards (../../)
        # secure_filename can be used on parts of path if constructing from user input, but here it's from DB.
        # However, direct use of send_from_directory with a subdirectory (UPLOAD_FOLDER) is generally safe.

        # Authorization: Check if the current user owns the company whose document is being requested
        company_id_str = filepath.split(os.sep, 1)[0]
        if not company_id_str.isdigit():
            flash("Invalid file path.", "error")
            return redirect(url_for('companies.list_companies')) # Or abort(400)

        company_id = int(company_id_str)
        doc_company = Company.query.get_or_404(company_id)
        if doc_company.user_id != current_user.id:
            flash("You are not authorized to access this file.", "error")
            return redirect(url_for('companies.list_companies')) # Or abort(403)
    except Exception as e: # Broad exception for path splitting or int conversion
        print(f"Error in serve_company_document path processing: {e}") # Log this
        flash("Invalid file path.", "error")
        return redirect(url_for('companies.list_companies')) # Or abort(404)

    # send_from_directory needs the base directory and then the relative path from that directory
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filepath, as_attachment=False)

@companies_bp.route('/document/<int:doc_id>/delete', methods=['POST'])
@login_required
def delete_document(doc_id):
    # Fetch the document record from the database
    doc_to_delete = CompanyDocument.query.get_or_404(doc_id)

    # Authorization: Ensure the user owns the company this document belongs to
    if doc_to_delete.company.user_id != current_user.id:
        flash("You are not authorized to delete this document.", "error")
        return redirect(url_for('companies.list_companies'))

    # Store company_id for redirection before we delete the object
    company_id = doc_to_delete.company_id

    try:
        # Step 1: Delete the physical file from the server
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], doc_to_delete.stored_filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Deleted file: {file_path}")
        else:
            print(f"WARNING: File to delete not found at path: {file_path}")

        # Step 2: Delete the database record
        db.session.delete(doc_to_delete)
        db.session.commit()
        flash("Document deleted successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting document: {e}", "error")
        print(f"ERROR: Could not delete document {doc_id}: {e}")

    return redirect(url_for('companies.company_dashboard', company_id=company_id))

@companies_bp.route('/<int:company_id>/fetch_news', methods=['POST'])
@login_required
def fetch_news(company_id):
    company = Company.query.get_or_404(company_id)
    if company.user_id != current_user.id:
        flash("You are not authorized to perform this action.", "error")
        return redirect(url_for('companies.list_companies'))

    # Call the background task
    task = fetch_company_news_task.delay(company.id)

    flash("Request received! Recent news is being fetched in the background. The page will reload when complete.", "info")

    # Redirect back to the same page with the task_id for polling
    return redirect(url_for('companies.scuttlebutt', 
                            company_id=company.id, 
                            task_id=task.id))

@companies_bp.route('/<int:company_id>/fetch_sec_filings', methods=['POST'])
@login_required
def fetch_sec_filings(company_id):
    company = Company.query.get_or_404(company_id)
    if company.user_id != current_user.id:
        flash("You are not authorized to perform this action.", "error")
        return redirect(url_for('companies.list_companies'))

    # Get the 'years' value from the form, defaulting to 5 if not found
    years_from_form = request.form.get('years', 5, type=int)
    
    # When you call .delay(), it returns a task object.
    task = fetch_sec_filings_task.delay(company.id, current_user.id, years_from_form)
    
    # Flash a message to give immediate feedback.
    flash(f"Request received! {years_from_form} year(s) of filings are being fetched in the background. The page will reload when complete.", "info")
            
    # Redirect back to the same page, but add the task_id to the URL as a query parameter.
    return redirect(url_for('companies.company_dashboard',
                            company_id=company.id,
                            task_id=task.id))
    
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
        return redirect(url_for('portfolio.position_detail', company_id=company_id))
    else:
        # Not in portfolio - redirect to add transaction
        flash(f'To add "{company.name}" to your portfolio, please record a BUY transaction.', 'info')
        return redirect(url_for('portfolio.add_transaction') + f'?company_id={company_id}')
 

@companies_bp.route('/<int:company_id>/scuttlebutt')
@login_required
def scuttlebutt(company_id):
    company = Company.query.get_or_404(company_id)
    if company.user_id != current_user.id:
        flash("You are not authorized to access this page.", "error")
        return redirect(url_for('companies.list_companies'))

    # Fetch saved articles for this company, newest first
    articles = company.articles.order_by(CompanyArticle.published_at.desc()).all()
    latest_analysis = company.scuttlebutt_analyses.order_by(ScuttlebuttAnalysis.generated_at.desc()).first()
    
    return render_template(
        'scuttlebutt.html',
        title=f"Digital Scuttlebutt for {company.name}",
        company=company,
        articles=articles,
        latest_analysis=latest_analysis 
    )

@companies_bp.route('/<int:company_id>/analyze_scuttlebutt', methods=['POST'])
@login_required
def analyze_scuttlebutt(company_id):
    company = Company.query.get_or_404(company_id)
    if company.user_id != current_user.id:
        flash("You are not authorized to perform this action.", "error")
        return redirect(url_for('companies.list_companies'))

    # Call the background task
    task = analyze_scuttlebutt_task.delay(company.id)

    # Redirect back to the Scuttlebutt page with the task_id for polling
    return redirect(url_for('companies.scuttlebutt', 
                            company_id=company.id, 
                            task_id=task.id))

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
    
@companies_bp.route('/<int:company_id>/porters-five-forces', methods=['GET', 'POST'])
@login_required
def porters_five_forces_analysis(company_id):
    company = Company.query.get_or_404(company_id)
    if company.user_id != current_user.id:
        flash("You are not authorized to access this page.", "error")
        return redirect(url_for('companies.list_companies'))

    analysis_type = 'PortersFiveForces'
    analysis = QualitativeAnalysis.query.filter_by(
        user_id=current_user.id,
        company_id=company.id,
        model_type=analysis_type
    ).first()

    if request.method == 'POST':
        content_data = {
            'threat_of_new_entrants': request.form.get('threat_of_new_entrants', ''),
            'bargaining_power_of_buyers': request.form.get('bargaining_power_of_buyers', ''),
            'bargaining_power_of_suppliers': request.form.get('bargaining_power_of_suppliers', ''),
            'threat_of_substitutes': request.form.get('threat_of_substitutes', ''),
            'industry_rivalry': request.form.get('industry_rivalry', '')
        }

        if analysis:
            analysis.content = content_data
        else:
            analysis = QualitativeAnalysis(
                user_id=current_user.id,
                company_id=company.id,
                model_type=analysis_type,
                content=content_data
            )
            db.session.add(analysis)

        try:
            db.session.commit()
            flash("Porter's Five Forces analysis saved successfully.", 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred while saving: {e}', 'error')

        # Preserve research workflow context if present
        project_id = request.args.get('project_id')
        step_index = request.args.get('step_index')
        if project_id and step_index:
            return redirect(url_for('companies.porters_five_forces_analysis',
                                  company_id=company.id,
                                  project_id=project_id,
                                  step_index=step_index))
        else:
            return redirect(url_for('companies.porters_five_forces_analysis', company_id=company.id))

    existing_content = analysis.content if analysis and analysis.content else {}

    return render_template(
        'porters_five_forces.html',
        title=f"Porter's Five Forces for {company.name}",
        company=company,
        analysis_content=existing_content
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
    company = Company.query.get_or_404(company_id)
    if company.user_id != current_user.id:
        abort(403) # Use abort for unauthorized actions

    competitor_id = request.form.get('competitor_id', type=int)
    if not competitor_id:
        flash('No competitor selected.', 'error')
        return redirect(url_for('companies.company_dashboard', company_id=company_id))

    competitor = Company.query.get_or_404(competitor_id)

    if competitor.user_id != current_user.id:
        abort(403)

    if competitor in company.competitors:
        flash(f'"{competitor.name}" is already a competitor.', 'warning')
    else:
        company.competitors.append(competitor)
        db.session.commit()
        flash(f'"{competitor.name}" added as a competitor.', 'success')

    return redirect(url_for('companies.company_dashboard', company_id=company_id))

@companies_bp.route('/<int:company_id>/remove_competitor/<int:competitor_id>', methods=['POST'])
@login_required
def remove_competitor(company_id, competitor_id):
    company = Company.query.get_or_404(company_id)
    if company.user_id != current_user.id:
        abort(403)

    competitor = Company.query.get_or_404(competitor_id)
    if competitor in company.competitors:
        company.competitors.remove(competitor)
        db.session.commit()
        flash(f'"{competitor.name}" removed from competitors.', 'info')

    return redirect(url_for('companies.company_dashboard', company_id=company_id))

@companies_bp.route('/<int:company_id>/edit', methods=['POST'])
@login_required
def edit_company(company_id):
    """Update company details including ticker symbol, name, sector, and industry"""
    company = Company.query.get_or_404(company_id)

    # Authorization check
    if company.user_id != current_user.id:
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
        flash('Company name and ticker symbol are required.', 'error')
        return redirect(url_for('companies.company_dashboard', company_id=company_id))

    # Check if ticker is changing and validate it
    ticker_changed = (ticker_symbol != company.ticker_symbol)
    if ticker_changed:
        # Validate ticker with Yahoo Finance
        validator = TickerValidator()
        validation_result = validator.validate_ticker(ticker_symbol)

        if not validation_result['valid']:
            flash(f'Invalid ticker symbol: {validation_result.get("error", "Could not validate ticker")}', 'error')
            return redirect(url_for('companies.company_dashboard', company_id=company_id))

        # Check for duplicate ticker in user's companies
        existing_company = Company.query.filter_by(
            user_id=current_user.id,
            ticker_symbol=ticker_symbol
        ).filter(Company.id != company_id).first()

        if existing_company:
            flash(f'You already have a company with ticker "{ticker_symbol}": {existing_company.name}', 'error')
            return redirect(url_for('companies.company_dashboard', company_id=company_id))

    # Update company fields
    old_name = company.name
    old_ticker = company.ticker_symbol

    company.name = name
    company.ticker_symbol = ticker_symbol
    company.summary = summary if summary else None
    company.industry = industry if industry else None

    # Handle sector
    if sector_name:
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

                flash('Portfolio positions updated with new ticker symbol.', 'info')

        if changes:
            flash(f'Company updated successfully: {", ".join(changes)}', 'success')
        else:
            flash('Company details saved.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error updating company: {str(e)}', 'error')

    return redirect(url_for('companies.company_dashboard', company_id=company_id))

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

