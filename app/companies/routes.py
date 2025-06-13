import os
import uuid
import yfinance as yf
from werkzeug.utils import secure_filename
from datetime import datetime

from flask import render_template, request, redirect, url_for, flash, current_app, send_from_directory
from flask_login import current_user, login_required
from app import db
from app.models import User, Company, CompanyDocument # Add other models if needed
from app.companies import companies_bp

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

@companies_bp.route('/', methods=['GET'])
@login_required
def list_companies():
    # Get all companies for the user
    all_user_companies = Company.query.filter_by(user_id=current_user.id).order_by(Company.name).all()
    
    # Get a set of IDs for the user's favorite companies for quick checking
    favorite_ids = {company.id for company in current_user.favorites.all()}

    # Partition the list of company objects into favorites and others
    favorite_companies = [company for company in all_user_companies if company.id in favorite_ids]
    other_companies = [company for company in all_user_companies if company.id not in favorite_ids]

    return render_template(
        'list_companies.html', 
        favorite_companies=favorite_companies,
        other_companies=other_companies,
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

@companies_bp.route('/<int:company_id>/documents', methods=['GET', 'POST']) # /companies/<id>/documents
@login_required
def manage_company_documents(company_id):
    company = Company.query.get_or_404(company_id)
    if company.user_id != current_user.id:
        flash("You are not authorized to manage documents for this company.", "error")
        return redirect(url_for('companies.list_companies'))

    if request.method == 'POST':
        if 'document_file' not in request.files: # Copied from previous implementation
            flash('No file part', 'error')
            return redirect(request.url)
        file = request.files['document_file']
        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(request.url)

        doc_group = request.form.get('document_group')
        doc_title = request.form.get('document_title')
        doc_date_str = request.form.get('document_date')
        doc_description = request.form.get('description')

        if not doc_group or not doc_title:
            flash('Document group and title are required.', 'error')
        elif file:
            original_fn = secure_filename(file.filename)
            file_ext = os.path.splitext(original_fn)[1].lower() # Get extension like .pdf
            allowed_extensions_str = {f".{ext}" for ext in current_app.config['ALLOWED_EXTENSIONS']}

            if file_ext not in allowed_extensions_str:
                flash(f'File type {file_ext} not allowed. Allowed types: {current_app.config["ALLOWED_EXTENSIONS"]}', 'error')
            else:
                stored_fn = f"{uuid.uuid4().hex}{file_ext}"
                company_specific_upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], str(company.id))
                os.makedirs(company_specific_upload_path, exist_ok=True)
                file_save_path = os.path.join(company_specific_upload_path, stored_fn)
                file.save(file_save_path)

                document_date_obj = None
                if doc_date_str:
                    try:
                        document_date_obj = datetime.strptime(doc_date_str, '%Y-%m-%d').date()
                    except ValueError:
                        flash('Invalid date format. Please use YYYY-MM-DD.', 'error')

                new_doc = CompanyDocument(
                    company_id=company.id, user_id=current_user.id,
                    original_filename=original_fn,
                    stored_filename=os.path.join(str(company.id), stored_fn),
                    document_group=doc_group, document_title=doc_title,
                    document_date=document_date_obj, description=doc_description
                )
                db.session.add(new_doc)
                db.session.commit()
                flash(f'Document "{original_fn}" uploaded successfully to group "{doc_group}".', 'success')
            return redirect(url_for('companies.manage_company_documents', company_id=company.id))

    documents_query = company.documents.order_by(CompanyDocument.document_group, CompanyDocument.document_date.desc(), CompanyDocument.document_title).all()    
    grouped_documents = {}
    for doc in documents_query:
        group = doc.document_group
        if group not in grouped_documents: grouped_documents[group] = []
        grouped_documents[group].append(doc)
        
    distinct_group_names_query = db.session.query(CompanyDocument.document_group)\
                                        .filter(CompanyDocument.user_id == current_user.id)\
                                        .distinct()\
                                        .order_by(CompanyDocument.document_group)\
                                        .all()
    distinct_group_names = [group[0] for group in distinct_group_names_query if group[0]]
    
                                         
    return render_template('company_documents.html', 
                           company=company, 
                           grouped_documents=grouped_documents,
                           distinct_group_names=distinct_group_names,
                           title=f"Documents for {company.name}")

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