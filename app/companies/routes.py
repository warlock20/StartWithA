import os
import uuid
from werkzeug.utils import secure_filename
from datetime import datetime

from flask import render_template, request, redirect, url_for, flash, current_app, send_from_directory
from flask_login import current_user, login_required
from app import db
from app.models import User, Company, CompanyDocument # Add other models if needed
from app.companies import companies_bp

@companies_bp.route('/', methods=['GET']) # Will be /companies/
@login_required
def list_companies():
    companies = Company.query.filter_by(user_id=current_user.id).order_by(Company.name).all()
    return render_template('list_companies.html', companies=companies, title=f"{current_user.username}'s Companies")

@companies_bp.route('/new', methods=['GET', 'POST']) # Will be /companies/new
@login_required
def new_company():
    if request.method == 'POST':
        name = request.form.get('name')
        ticker_symbol = request.form.get('ticker_symbol', '').upper()

        if not name or not ticker_symbol:
            flash('Company name and ticker symbol are required.', 'error')
            return render_template('new_company.html', title="Add New Company", name=name, ticker_symbol=ticker_symbol)


        existing_company_by_name = Company.query.filter_by(name=name, user_id=current_user.id).first()
        existing_company_by_ticker = Company.query.filter_by(ticker_symbol=ticker_symbol, user_id=current_user.id).first()

        if existing_company_by_name:
            flash(f'You already have a company named "{name}".', 'error')
        elif existing_company_by_ticker:
            flash(f'You already have a company with ticker "{ticker_symbol}".', 'error')
        else:
            company = Company(name=name, ticker_symbol=ticker_symbol, creator=current_user)
            db.session.add(company)
            db.session.commit()
            flash(f'Company "{name}" ({ticker_symbol}) added successfully.', 'success')
            next_url = request.args.get('next')
            if next_url:
                return redirect(next_url)
            return redirect(url_for('companies.list_companies'))

        return render_template('new_company.html', title="Add New Company", name=name, ticker_symbol=ticker_symbol)
    return render_template('new_company.html', title="Add New Company")

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

    return render_template('company_documents.html', 
                           company=company, 
                           grouped_documents=grouped_documents,
                           title=f"Documents for {company.name}")

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