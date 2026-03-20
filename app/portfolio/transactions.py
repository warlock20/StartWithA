import os
import tempfile
from decimal import Decimal, InvalidOperation
import json
import logging
import datetime
from flask import request, render_template, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload

from app.portfolio import portfolio_bp
from app.models import (
                        Company,Transaction, PortfolioPosition,
                        ResearchProject, update_portfolio_position)
from app import db
from app.services.portfolio_importer import PortfolioImportError
from app.services.background_tasks import BackgroundTaskService
from app.services.currency_service import CurrencyService
from app.services.transaction_service import TransactionService
from app.services.cash_service import CashService
from app.utils.time_utils import now_utc, parse_date_to_date_object

logger = logging.getLogger(__name__)

@portfolio_bp.route('/transactions')
@login_required
def transactions():
    """View all transactions with client-side filtering"""
    # Load all transactions with company eager loading
    all_transactions = Transaction.query.filter_by(
        user_id=current_user.id
    ).options(
        joinedload(Transaction.company)
    ).order_by(Transaction.date.desc()).all()

    # Get user currency settings
    currency_symbol = CurrencyService.get_currency_symbol(current_user.base_currency)

    # Serialize for Tabulator
    transactions_json = json.dumps([{
        'id': txn.id,
        'date': txn.date.strftime('%Y-%m-%d'),
        'type': txn.type,
        'ticker': txn.company.ticker_symbol if txn.company else '---',
        'company_name': txn.company.name if txn.company else ('Deposit' if txn.type == 'DEPOSIT' else 'Withdrawal' if txn.type == 'WITHDRAWAL' else '---'),
        'company_id': txn.company_id,
        'shares': float(txn.quantity) if txn.quantity else 0,
        'price': float(txn.price_per_share) if txn.price_per_share else 0,
        'fees': float(txn.fees) if txn.fees else 0,
        'total': float(txn.cash_amount or 0) if txn.type in ('DEPOSIT', 'WITHDRAWAL') else (float(txn.total_value) if txn.total_value else 0),
        'notes': txn.notes or '',
        'bought_without_research': bool(txn.bought_without_research),
        'edit_url': url_for('portfolio.edit_transaction', transaction_id=txn.id),
        'delete_url': url_for('portfolio.delete_transaction', transaction_id=txn.id),
    } for txn in all_transactions])

    return render_template('transactions.html',
                          transactions=all_transactions,
                          transactions_json=transactions_json,
                          currency_symbol=currency_symbol)

@portfolio_bp.route('/transactions/import', methods=['POST'])
@login_required
def import_transactions():
    if 'file' not in request.files:
        flash('No file part', 'error')
        return redirect(url_for('portfolio.dashboard'))

    file = request.files['file']

    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(url_for('portfolio.dashboard'))

    original_filename = file.filename
    if not original_filename.lower().endswith(('.csv', '.xls', '.xlsx')):
        flash('Unsupported file format. Use CSV or Excel.', 'error')
        return redirect(url_for('portfolio.dashboard'))

    tmp_path = None
    try:
        suffix = os.path.splitext(original_filename)[1]
        upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'imports')
        os.makedirs(upload_dir, exist_ok=True)

        with tempfile.NamedTemporaryFile(dir=upload_dir, suffix=suffix, delete=False) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        task_id = BackgroundTaskService.start_portfolio_import(
            user_id=current_user.id,
            file_path=tmp_path
        )

        return redirect(url_for('portfolio.import_loading', task_id=task_id))

    except Exception as e:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        flash(f"Failed to start import: {str(e)}", "error")
        return redirect(url_for('portfolio.dashboard'))


@portfolio_bp.route('/import/loading/<task_id>')
@login_required
def import_loading(task_id):
    """Show loading page while import runs in background."""
    return render_template('import_loading.html', task_id=task_id)


@portfolio_bp.route('/import/complete/<task_id>')
@login_required
def import_complete(task_id):
    """Flash the import result and redirect to dashboard."""
    task_status = BackgroundTaskService.get_task_status(task_id)
    if task_status and task_status['status'] == 'completed':
        result = task_status.get('result', {})
        msg = result.get('message', 'Import completed!') if result else 'Import completed!'
        flash(msg, 'success')
    elif task_status and task_status['status'] == 'failed':
        flash(f"Import failed: {task_status.get('error', 'Unknown error')}", 'error')
    return redirect(url_for('portfolio.dashboard'))


@portfolio_bp.route('/import/status/<task_id>')
@login_required
def import_status(task_id):
    """Check the status of a running import task. Returns JSON for AJAX polling."""
    task_status = BackgroundTaskService.get_task_status(task_id)

    if not task_status:
        return jsonify({'state': 'NOT_FOUND', 'current': 0, 'total': 100, 'status': 'Task not found'})

    response = {'current': 0, 'total': 100, 'status': ''}

    if task_status['status'] == 'pending':
        response['state'] = 'PENDING'
        response['status'] = 'Import queued, waiting to start...'
        response['current'] = 10
    elif task_status['status'] == 'running':
        response['state'] = 'STARTED'
        response['status'] = 'Importing transactions and fetching company data...'
        response['current'] = 50
    elif task_status['status'] == 'completed':
        response['state'] = 'SUCCESS'
        response['current'] = 100
        result = task_status.get('result', {})
        response['status'] = result.get('message', 'Import completed!') if result else 'Import completed!'
        response['result'] = result
    elif task_status['status'] == 'failed':
        response['state'] = 'FAILURE'
        response['current'] = 100
        response['status'] = 'Import failed'
        response['error'] = task_status.get('error', 'Unknown error')

    return jsonify(response)

@portfolio_bp.route('/transactions/reset', methods=['POST'])
@login_required
def reset_portfolio():
    """
    DANGER: Deletes ALL transactions and portfolio positions for the current user.
    This cannot be undone.
    """
    try:
        # 1. Delete all Portfolio Positions (Derived data)
        num_positions = db.session.query(PortfolioPosition).filter_by(
            user_id=current_user.id
        ).delete()
        
        # 2. Delete all Transactions (Source data)
        num_transactions = db.session.query(Transaction).filter_by(
            user_id=current_user.id
        ).delete()

        # 3. Reset cash balance
        current_user.cash_balance = 0
        current_user.cash_setup_complete = False

        db.session.commit()

        flash(f"Portfolio reset complete. Deleted {num_transactions} transactions and {num_positions} positions.", "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"Error resetting portfolio: {str(e)}", "error")
        
    return redirect(url_for('portfolio.dashboard'))

@portfolio_bp.route('/debug/force-resync')
@login_required
def force_resync():
    """
    Debug Tool: Forces a recalculation of all portfolio positions
    using existing transactions.
    """
    try:
        # 1. Get all company IDs that have transactions for this user
        company_ids = db.session.query(Transaction.company_id).filter_by(
            user_id=current_user.id
        ).distinct().all()
        company_ids = [c[0] for c in company_ids]  # Flatten list of tuples
        
        if not company_ids:
            flash("No transactions found to sync.", "warning")
            return redirect(url_for('portfolio.dashboard'))

        # 2. Force Recalculate Positions
        recalculated = 0
        for comp_id in company_ids:
            # FIX: Fetch the actual latest transaction from the DB
            # This ensures the object is attached to the session correctly
            latest_txn = Transaction.query.filter_by(
                user_id=current_user.id, 
                company_id=comp_id
            ).order_by(Transaction.date.desc()).first()
            
            if latest_txn:
                # Pass the real transaction object
                update_portfolio_position(latest_txn)
                recalculated += 1
            
        # Commit all position updates
        db.session.commit()

        # Recalculate cash balance
        CashService.recalculate_cash_balance(current_user.id)

        flash(f"Resync Complete: Recalculated positions for {recalculated} companies based on {len(company_ids)} transaction sets.", "success")
            
    except Exception as e:
        db.session.rollback()
        # Log the full error for debugging
        print(f"Resync Error: {str(e)}") 
        flash(f"Debug failed: {str(e)}", 'error')
        
    return redirect(url_for('portfolio.dashboard'))

@portfolio_bp.route('/transaction/new', methods=['GET', 'POST'])
@portfolio_bp.route('/transaction/add', methods=['GET', 'POST'])
@login_required
def add_transaction():
    """Add a new transaction using TransactionService"""
    warnings = []

    if request.method == 'POST':
        # Use TransactionService for all business logic
        result = TransactionService.create_transaction(
            user_id=current_user.id,
            form_data=request.form,
            user_base_currency=current_user.base_currency
        )

        if result.success:
            flash(result.message, 'success')
            for warning in result.warnings:
                flash(warning, 'info')

            # Redirect based on transaction type
            if 'sell_postmortem' in result.redirect_url:
                flash('Please complete a post-mortem analysis for this sale', 'info')

            return redirect(url_for(result.redirect_url, **result.redirect_kwargs))
        else:
            flash(result.error, 'error')
            # Re-render form with warnings if validation failed
            if result.warnings:
                companies = Company.query.filter_by(user_id=current_user.id).order_by(Company.name).all()
                return render_template('add_transaction.html',
                                      companies=companies,
                                      warnings=result.warnings,
                                      show_warning=True,
                                      form_data=request.form,
                                      user_currency=current_user.base_currency,
                                      currency_symbol=CurrencyService.get_currency_symbol(current_user.base_currency))
            return redirect(url_for('portfolio.add_transaction'))

    # GET request - show form
    companies = Company.query.filter_by(user_id=current_user.id).order_by(Company.name).all()

    # Get existing positions for the user
    existing_positions = {}
    positions = PortfolioPosition.query.filter_by(user_id=current_user.id).all()
    for pos in positions:
        if pos.total_shares > 0:
            existing_positions[pos.company_id] = {
                'shares': pos.total_shares,
                'avg_cost': float(pos.average_cost_basis) if pos.average_cost_basis else 0,
                'ticker': pos.company.ticker_symbol
            }

    # Check which companies have research
    companies_with_research = set()
    research_projects = ResearchProject.query.filter_by(user_id=current_user.id).all()
    for rp in research_projects:
        companies_with_research.add(rp.company_id)

    # Get company_id from query params if provided
    preselected_company_id = request.args.get('company_id', type=int)

    user_currency = current_user.base_currency
    currency_symbol = CurrencyService.get_currency_symbol(user_currency)

    return render_template('add_transaction.html',
                          companies=companies,
                          warnings=warnings,
                          show_warning=False,
                          form_data=None,
                          existing_positions=existing_positions,
                          companies_with_research=companies_with_research,
                          preselected_company_id=preselected_company_id,
                          user_currency=user_currency,
                          currency_symbol=currency_symbol)

@portfolio_bp.route('/transaction/<int:transaction_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_transaction(transaction_id):
    """Edit an existing transaction"""
    transaction = Transaction.query.filter_by(
        id=transaction_id,
        user_id=current_user.id
    ).first_or_404()

    if request.method == 'POST':
        try:
            # Get form data (similar to add_transaction)
            date_str = request.form.get('date')
            quantity = request.form.get('quantity', type=int)
            price_per_share = request.form.get('price_per_share')
            fees = request.form.get('fees', '0')
            notes = request.form.get('notes', '').strip()

            # Validation
            if not all([date_str, quantity, price_per_share]):
                flash('Please fill in all required fields', 'error')
                return redirect(url_for('portfolio.edit_transaction', transaction_id=transaction_id))

            # Parse and validate date
            transaction_date = parse_date_to_date_object(date_str)
            if not transaction_date:
                flash('Invalid date format', 'error')
                return redirect(url_for('portfolio.edit_transaction', transaction_id=transaction_id))

            # Parse numeric values
            try:
                price_per_share = Decimal(price_per_share)
                fees = Decimal(fees) if fees else Decimal('0.00')
            except (InvalidOperation, ValueError):
                flash('Invalid price or fees amount', 'error')
                return redirect(url_for('portfolio.edit_transaction', transaction_id=transaction_id))

            # Update transaction
            transaction.date = transaction_date
            transaction.quantity = quantity
            transaction.price_per_share = price_per_share
            transaction.fees = fees
            transaction.notes = notes

            # Recalculate portfolio position
            update_portfolio_position(transaction)

            db.session.commit()

            # Recalculate cash balance
            CashService.recalculate_cash_balance(current_user.id)

            flash('Transaction updated successfully', 'success')
            return redirect(url_for('portfolio.transactions'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error updating transaction: {str(e)}', 'error')
            return redirect(url_for('portfolio.edit_transaction', transaction_id=transaction_id))

    # GET request
    return render_template('edit_transaction.html', transaction=transaction)


@portfolio_bp.route('/transaction/<int:transaction_id>/delete', methods=['POST'])
@login_required
def delete_transaction(transaction_id):
    """Delete a transaction"""
    transaction = Transaction.query.filter_by(
        id=transaction_id,
        user_id=current_user.id
    ).first_or_404()

    try:
        company_id = transaction.company_id
        company_ticker = transaction.company.ticker_symbol if transaction.company else '---'
        txn_type = transaction.type

        # Delete transaction
        db.session.delete(transaction)
        db.session.commit()

        # Recalculate position for this company (skip for DEPOSIT/WITHDRAWAL)
        if txn_type not in ('DEPOSIT', 'WITHDRAWAL') and company_id:
            temp_transaction = Transaction(
                user_id=current_user.id,
                company_id=company_id,
                type='BUY',  # Doesn't matter, just for recalculation
                date=now_utc().date(),
                quantity=0,
                price_per_share=0
            )
            update_portfolio_position(temp_transaction)
            db.session.commit()

        # Recalculate cash balance
        CashService.recalculate_cash_balance(current_user.id)

        flash(f'Transaction for {company_ticker} deleted successfully', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting transaction: {str(e)}', 'error')

    return redirect(url_for('portfolio.transactions'))

