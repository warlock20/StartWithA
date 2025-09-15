import os
import uuid
import yfinance as yf
from werkzeug.utils import secure_filename
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, current_app, send_from_directory, abort
from flask_login import current_user, login_required
from app import db, cache
from app.models import User, Company, CompanyDocument, DestinationCheckpoint, ResearchSession, CompanyArticle, ScuttlebuttAnalysis, QualitativeAnalysis, FinancialData
from app.companies import companies_bp
from app.tasks import fetch_financial_data_task

from itertools import groupby

from app.tasks import fetch_sec_filings_task, fetch_company_news_task, analyze_scuttlebutt_task

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
    Fetches market data for a given ticker using yfinance.
    The results of this function will be cached.
    """
    print(f"--- MAKING LIVE API CALL for {ticker} ---") # This will only print if not cached
    try:
        ticker_info = yf.Ticker(ticker).info
        # We only need a few key pieces of data
        market_cap = ticker_info.get('marketCap')
        # You could also get other data like 'currentPrice', 'dayHigh', 'dayLow' here
        return {
            'marketCap': market_cap,
        }
    except Exception as e:
        print(f"yfinance lookup failed for {ticker}: {e}")

@companies_bp.route('/', methods=['GET'])
@login_required
def list_companies():
    # --- 1. Fetch all necessary data in efficient queries ---

    # Get all companies for the current user
    all_user_companies = Company.query.filter_by(user_id=current_user.id).all()

    # Get sets of IDs for categorization
    favorite_ids = {c.id for c in current_user.favorites.all()}
    portfolio_ids = {c.id for c in all_user_companies if c.is_in_portfolio}

    # Get sets of company IDs that have a specific analysis completed
    completed_checklist_ids = {s.company_id for s in ResearchSession.query.filter_by(user_id=current_user.id, status='completed').all()}
    swot_analysis_ids = {a.company_id for a in QualitativeAnalysis.query.filter_by(user_id=current_user.id, model_type='SWOT').all()}
    dest_analysis_ids = {c.company_id for c in DestinationCheckpoint.query.filter_by(user_id=current_user.id).all()}

    # --- 2. Build the enriched data structure for the template ---
    companies_data_list = []
    for company in all_user_companies:
        data = {
            'company_obj': company,
            'has_completed_checklist': company.id in completed_checklist_ids,
            'has_swot': company.id in swot_analysis_ids,
            'has_destination_analysis': company.id in dest_analysis_ids,
        }
        companies_data_list.append(data)

    # --- 3. Partition the enriched data into the three lists ---
    portfolio_companies_data = [d for d in companies_data_list if d['company_obj'].id in portfolio_ids]
    favorite_companies_data = [d for d in companies_data_list if d['company_obj'].id in favorite_ids and d['company_obj'].id not in portfolio_ids]
    other_companies_data = [d for d in companies_data_list if d['company_obj'].id not in portfolio_ids and d['company_obj'].id not in favorite_ids]

    # Sort each list by company name
    portfolio_companies_data.sort(key=lambda x: x['company_obj'].name)
    favorite_companies_data.sort(key=lambda x: x['company_obj'].name)
    other_companies_data.sort(key=lambda x: x['company_obj'].name)

    return render_template(
        'list_companies.html', 
        portfolio_companies_data=portfolio_companies_data,
        favorite_companies_data=favorite_companies_data,
        other_companies_data=other_companies_data,
        portfolio_ids=portfolio_ids,
        favorite_ids=favorite_ids,
        # We no longer need to pass eligible_for_da_ids as it's part of the new structure
        title=f"{current_user.username}'s Companies"
    )

@companies_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_company():
    if request.method == 'POST':
        base_ticker = request.form.get('base_ticker', '').upper()
        exchange_suffix = request.form.get('exchange_suffix', '')

        if not base_ticker:
            flash('Base Ticker Symbol is required.', 'error')
            return redirect(url_for('companies.new_company'))
        
        # Combine the base ticker and suffix to create the full yfinance ticker
        full_ticker_symbol = f"{base_ticker}{exchange_suffix}"

        try:
            company_ticker = yf.Ticker(full_ticker_symbol)
            info = company_ticker.info
            
            if info and info.get('longName'):
                # --- SUCCESSFUL LOOKUP PATH ---
                company_name = info.get('longName')
                company_summary = info.get('longBusinessSummary', 'No summary available.')
                company_sector = info.get('sector', 'N/A')
                company_industry = info.get('industry', 'N/A')
                # Check if user already has this company
                existing_company = Company.query.filter_by(ticker_symbol=full_ticker_symbol, user_id=current_user.id).first()
                if existing_company:
                    flash(f'You have already added "{company_name}" ({full_ticker_symbol}) to your list.', 'info')
                    return redirect(url_for('companies.list_companies'))
                
                return render_template('confirm_company.html',
                                       title="Confirm Company",
                                       ticker=full_ticker_symbol,
                                       name=company_name,
                                       summary=company_summary,
                                       sector=company_sector,    
                                       industry=company_industry 
                                       )
            else:
                # --- FAILED LOOKUP / MANUAL OVERRIDE PATH ---
                flash(f'Could not automatically find details for ticker "{full_ticker_symbol}". Please enter the company name manually.', 'warning')
                return render_template('new_company_manual.html',
                                       title="Add Company Manually",
                                       ticker=full_ticker_symbol) # Pass the full ticker
        except Exception as e:
            print(f"yfinance lookup error for ticker {full_ticker_symbol}: {e}")
            flash(f'An error occurred while looking up ticker "{full_ticker_symbol}". Please enter details manually.', 'warning')
            return render_template('new_company_manual.html',
                                   title="Add Company Manually",
                                   ticker=full_ticker_symbol)

    # For GET request, pass the exchanges dictionary to the template
    return render_template('new_company.html', 
                           title="Add New Company", 
                           exchanges=EXCHANGES)

@companies_bp.route('/add_confirmed', methods=['POST'])
@login_required
def add_company_confirmed():
    for key, value in request.form.items():
        print(f"  - {key}: '{value}'")
        
    name = request.form.get('name')
    ticker_symbol = request.form.get('ticker_symbol')
    summary = request.form.get('summary')
    sector = request.form.get('sector')
    industry = request.form.get('industry')
    # Redundant check, but good for safety if this route is accessed directly
    existing_company = Company.query.filter_by(ticker_symbol=ticker_symbol, user_id=current_user.id).first()
    if existing_company:
        flash(f'"{name}" ({ticker_symbol}) is already in your list.', 'info')
        return redirect(url_for('companies.list_companies'))

    if name and ticker_symbol:
        company = Company(name=name, ticker_symbol=ticker_symbol, summary=summary, sector=sector, industry=industry, creator=current_user)
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
        # Deleting the company will now also delete its research sessions,
        # documents, and favorite entries due to cascade settings.
        db.session.delete(company_to_delete)
        db.session.commit()
        flash(f'Company "{company_to_delete.name}" and all its data have been deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting company: {str(e)}', 'error')

    return redirect(url_for('companies.list_companies'))


# In app/companies/routes.py
# Make sure datetime, uuid, secure_filename, os, etc. are imported at the top of the file

@companies_bp.route('/<int:company_id>/add_document', methods=['POST'])
@login_required
def add_document(company_id):
    company = Company.query.get_or_404(company_id)
    if company.user_id != current_user.id:
        abort(403)

    # --- Basic File Checks ---
    if 'document_file' not in request.files:
        flash('No file part in request.', 'error')
        return redirect(url_for('companies.manage_company_documents', company_id=company_id))
    
    file = request.files['document_file']
    if file.filename == '':
        flash('No file selected for upload.', 'error')
        return redirect(url_for('companies.manage_company_documents', company_id=company_id))

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
                        return redirect(url_for('companies.manage_company_documents', company_id=company_id))
                
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
    
    return redirect(url_for('companies.manage_company_documents', company_id=company_id))

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

    return render_template(
        'company_documents.html', 
        company=company, 
        grouped_documents=grouped_documents,
        distinct_group_names=distinct_group_names,
        intrinsic_display_value=intrinsic_display_value,
        intrinsic_unit=intrinsic_unit,
        current_competitors=current_competitors,
        potential_competitors=potential_competitors,
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

# Note: The path for serving files might be better as absolute or handled by a dedicated 'uploads' blueprint
# For now, placing it under the /companies prefix.
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

    return redirect(request.referrer or url_for('companies.manage_company_documents', company_id=company.id))

# In app/companies/routes.py
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

    return redirect(url_for('companies.manage_company_documents', company_id=company_id))

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
    return redirect(url_for('companies.manage_company_documents', 
                            company_id=company.id, 
                            task_id=task.id))
    
    
@companies_bp.route('/<int:company_id>/add_checkpoint', methods=['POST'])
@login_required
def add_checkpoint(company_id):
    company = Company.query.get_or_404(company_id)
    # Authorization check
    if company.user_id != current_user.id:
        flash("You are not authorized to modify this company.", "error")
        return redirect(url_for('companies.list_companies'))

    metric = request.form.get('metric')
    expectation = request.form.get('expectation')
    target_date_str = request.form.get('target_date')

    if not metric or not expectation or not target_date_str:
        flash("All fields are required to add a checkpoint.", "error")
        return redirect(url_for('companies.manage_company_documents', company_id=company_id))

    try:
        target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()

        new_checkpoint = DestinationCheckpoint(
            company_id=company.id,
            user_id=current_user.id,
            metric=metric,
            expectation=expectation,
            target_date=target_date
            # Status defaults to 'Active' as defined in the model
        )
        db.session.add(new_checkpoint)
        db.session.commit()
        flash("New destination analysis checkpoint added successfully.", "success")

    except ValueError:
        flash("Invalid date format. Please use YYYY-MM-DD.", "error")
    except Exception as e:
        db.session.rollback()
        flash(f"An error occurred: {e}", "error")

    return redirect(url_for('companies.destination_analysis', company_id=company.id))

@companies_bp.route('/<int:company_id>/destination_analysis')
@login_required
def destination_analysis(company_id):
    company = Company.query.get_or_404(company_id)
    if company.user_id != current_user.id:
        flash("You are not authorized to access this page.", "error")
        return redirect(url_for('companies.list_companies'))

    checkpoints = company.destination_checkpoints.order_by(DestinationCheckpoint.target_date.asc()).all()

    return render_template('destination_analysis.html', 
                           company=company, 
                           checkpoints=checkpoints,
                           title=f"Destination Analysis for {company.name}")
    
@companies_bp.route('/checkpoint/<int:checkpoint_id>/update', methods=['POST'])
@login_required
def update_checkpoint(checkpoint_id):
    checkpoint = DestinationCheckpoint.query.get_or_404(checkpoint_id)

    # Authorization check
    if checkpoint.user_id != current_user.id:
        flash("You are not authorized to update this checkpoint.", "error")
        return redirect(url_for('companies.list_companies'))

    # Get data from the form
    new_status = request.form.get('status')
    outcome_notes = request.form.get('outcome_notes')

    # Update the checkpoint object
    checkpoint.status = new_status
    checkpoint.outcome_notes = outcome_notes

    try:
        db.session.commit()
        print(f"  - COMMIT SUCCEEDED. New status in DB should be: '{checkpoint.status}'")
        flash("Checkpoint updated successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating checkpoint: {e}", "error")

    return redirect(url_for('companies.destination_analysis', company_id=checkpoint.company_id)) 

@companies_bp.route('/checkpoint/<int:checkpoint_id>/delete', methods=['POST'])
@login_required
def delete_checkpoint(checkpoint_id):
    checkpoint = DestinationCheckpoint.query.get_or_404(checkpoint_id)

    # Authorization check
    if checkpoint.user_id != current_user.id:
        flash("You are not authorized to delete this checkpoint.", "error")
        return redirect(url_for('companies.list_companies'))

    company_id = checkpoint.company_id # Store for redirect before deleting
    try:
        db.session.delete(checkpoint)
        db.session.commit()
        flash("Checkpoint deleted successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting checkpoint: {e}", "error")

    return redirect(url_for('companies.destination_analysis', company_id=company_id))

@companies_bp.route('/checkpoint/<int:checkpoint_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_checkpoint(checkpoint_id):
    checkpoint = DestinationCheckpoint.query.get_or_404(checkpoint_id)

    # Authorization check
    if checkpoint.user_id != current_user.id:
        flash("You are not authorized to edit this checkpoint.", "error")
        return redirect(url_for('companies.list_companies'))

    if request.method == 'POST':
        # Handle the form submission for updating
        metric = request.form.get('metric')
        expectation = request.form.get('expectation')
        target_date_str = request.form.get('target_date')

        if not metric or not expectation or not target_date_str:
            flash("Metric, Expectation, and Target Date are required.", "error")
            # Re-render the edit form with an error
            return render_template('companies/edit_checkpoint.html', title="Edit Checkpoint", checkpoint=checkpoint)

        try:
            checkpoint.metric = metric
            checkpoint.expectation = expectation
            checkpoint.target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
            db.session.commit()
            flash("Checkpoint updated successfully.", "success")
            return redirect(url_for('companies.destination_analysis', company_id=checkpoint.company_id))
        except ValueError:
            flash("Invalid date format. Please use YYYY-MM-DD.", "error")
        except Exception as e:
            db.session.rollback()
            flash(f"Error updating checkpoint: {e}", "error")

    # GET request: Show the edit form, pre-filled with existing data
    return render_template('edit_checkpoint.html', 
                           title="Edit Checkpoint", 
                           checkpoint=checkpoint)

@companies_bp.route('/<int:company_id>/toggle_portfolio', methods=['POST'])
@login_required
def toggle_portfolio(company_id):
    company = Company.query.get_or_404(company_id)
    # Authorization check
    if company.user_id != current_user.id:
        flash("You are not authorized to modify this company.", "error")
        return redirect(url_for('companies.list_companies'))

    # Flip the boolean status
    company.is_in_portfolio = not company.is_in_portfolio

    try:
        db.session.commit()
        status = "added to" if company.is_in_portfolio else "removed from"
        flash(f'"{company.name}" has been {status} your active portfolio.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f"An error occurred: {e}", "error")

    return redirect(request.referrer or url_for('companies.list_companies'))  

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
    company = Company.query.get_or_404(company_id)
    if company.user_id != current_user.id:
        flash("You are not authorized to perform this action.", "error")
        return redirect(url_for('companies.list_companies'))

    # Call the background task, passing only the company ID
    task = fetch_financial_data_task.delay(company.id)

    # Redirect back to the new financials page with the task_id for polling
    # We will create this page in the next step.
    return redirect(url_for('companies.financials', 
                            company_id=company.id, 
                            task_id=task.id))
 
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
    if competitor_id:
        competitor = Company.query.get_or_404(competitor_id)
        if competitor.user_id == current_user.id and competitor not in company.competitors:
            company.competitors.append(competitor)
            db.session.commit()
            flash(f'"{competitor.name}" added as a competitor.', 'success')

    return redirect(url_for('companies.manage_company_documents', company_id=company_id))

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

    return redirect(url_for('companies.manage_company_documents', company_id=company_id))

# API endpoints for company search modal
@companies_bp.route('/api/companies/search')
@login_required
def api_search_companies():
    """AJAX endpoint for searching companies - searches both user's companies and Yahoo Finance"""
    from flask import jsonify

    query = request.args.get('q', '').strip()
    if len(query) < 1:
        return jsonify({'user_companies': [], 'yahoo_suggestion': None})

    # Search in user's existing companies by name and ticker
    user_companies = Company.query.filter(
        Company.user_id == current_user.id,
        db.or_(
            Company.name.ilike(f'%{query}%'),
            Company.ticker_symbol.ilike(f'%{query}%')
        )
    ).order_by(Company.name).limit(10).all()

    user_company_data = []
    for company in user_companies:
        user_company_data.append({
            'id': company.id,
            'name': company.name,
            'ticker_symbol': company.ticker_symbol,
            'industry': company.industry,
            'sector': company.sector,
            'source': 'existing'
        })

    # If query looks like a ticker (short, uppercase), try Yahoo Finance lookup
    yahoo_suggestion = None
    if len(query) <= 6 and query.replace('.', '').isalnum():
        try:
            ticker_symbol = query.upper()
            # Check if this ticker already exists for the user
            existing = Company.query.filter_by(
                ticker_symbol=ticker_symbol,
                user_id=current_user.id
            ).first()

            if not existing:
                company_ticker = yf.Ticker(ticker_symbol)
                info = company_ticker.info

                if info and info.get('longName'):
                    yahoo_suggestion = {
                        'ticker_symbol': ticker_symbol,
                        'name': info.get('longName'),
                        'industry': info.get('industry', ''),
                        'sector': info.get('sector', ''),
                        'summary': info.get('longBusinessSummary', ''),
                        'source': 'yahoo_finance'
                    }
        except Exception as e:
            print(f"Yahoo Finance lookup error for {query}: {e}")
            pass

    return jsonify({
        'user_companies': user_company_data,
        'yahoo_suggestion': yahoo_suggestion
    })

@companies_bp.route('/api/companies/create', methods=['POST'])
@login_required
def api_create_company():
    """AJAX endpoint for creating new companies"""
    from flask import jsonify

    try:
        data = request.get_json()

        name = data.get('name', '').strip()
        ticker_symbol = data.get('ticker_symbol', '').strip().upper()
        industry = data.get('industry', '').strip() or None
        sector = data.get('sector', '').strip() or None

        if not name:
            return jsonify({'success': False, 'error': 'Company name is required'})

        # Check if company with same name or ticker already exists for this user
        existing = Company.query.filter(
            Company.user_id == current_user.id,
            db.or_(
                Company.name.ilike(name),
                db.and_(Company.ticker_symbol == ticker_symbol, ticker_symbol != '')
            )
        ).first()

        if existing:
            return jsonify({
                'success': False,
                'error': 'Company with this name or ticker already exists'
            })

        # Create new company
        company = Company(
            user_id=current_user.id,
            name=name,
            ticker_symbol=ticker_symbol if ticker_symbol else None,
            industry=industry,
            sector=sector
        )

        db.session.add(company)
        db.session.commit()

        return jsonify({
            'success': True,
            'company': {
                'id': company.id,
                'name': company.name,
                'ticker_symbol': company.ticker_symbol,
                'industry': company.industry,
                'sector': company.sector
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})            