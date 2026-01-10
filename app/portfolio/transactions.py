from decimal import Decimal, InvalidOperation
import logging
import datetime
from flask import request, render_template, redirect, url_for, flash
from flask_login import login_required, current_user

from app.portfolio import portfolio_bp
from app.models import ( 
                        Company,Transaction, PortfolioPosition, 
                        ResearchProject, update_portfolio_position)
from app import db
from app.constants import TRANSACTIONS_PER_PAGE
from app.services.portfolio_importer import PortfolioImporter, PortfolioImportError
from app.services.currency_service import CurrencyService
from app.services.transaction_service import TransactionService
from app.constants import TRANSACTIONS_PER_PAGE
from app.utils.time_utils import now_utc

logger = logging.getLogger(__name__)

@portfolio_bp.route('/transactions')
@login_required
def transactions():
    """View all transactions with filtering and pagination"""
    # Get filter parameters
    company_id = request.args.get('company_id', type=int)
    transaction_type = request.args.get('type')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    page = request.args.get('page', 1, type=int)
    per_page = TRANSACTIONS_PER_PAGE

    # Build query
    query = Transaction.query.filter_by(user_id=current_user.id)

    if company_id:
        query = query.filter_by(company_id=company_id)

    if transaction_type:
        query = query.filter_by(type=transaction_type)

    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            query = query.filter(Transaction.date >= start_date_obj)
        except ValueError:
            pass

    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(Transaction.date <= end_date_obj)
        except ValueError:
            pass

    # Get transactions with pagination
    pagination = query.order_by(Transaction.date.desc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    transactions = pagination.items

    # Get all companies for filter dropdown
    companies = Company.query.filter_by(user_id=current_user.id).order_by(Company.name).all()

    # Get user currency settings
    user_currency = current_user.base_currency
    currency_symbol = CurrencyService.get_currency_symbol(user_currency)

    return render_template('transactions.html',
                          transactions=transactions,
                          pagination=pagination,
                          companies=companies,
                          user_currency=user_currency,
                          currency_symbol=currency_symbol)

@portfolio_bp.route('/transactions/import', methods=['POST'])
def import_transactions():
    if 'file' not in request.files:
        flash('No file part', 'error')
        return redirect(url_for('portfolio.dashboard'))
    
    file = request.files['file']
    
    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(url_for('portfolio.index'))
    
    try:
        importer = PortfolioImporter(current_user.id)
        count = importer.process_file(file)
        
        force_resync()
        
        flash(f"Successfully imported {count} transactions!", "success")
    except PortfolioImportError as e:
        flash(f"Import Failed: {str(e)}", "error")
    except Exception as e:
        flash(f"System Error: {str(e)}", "error")
        
    return redirect(url_for('portfolio.dashboard'))

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

            # Redirect based on transaction type
            if 'sell_postmortem' in result.redirect_url:
                flash('Please complete a post-mortem analysis for this sale', 'info')

            return redirect(url_for(result.redirect_url))
        else:
            flash(result.error, 'error')
            # Re-render form with warnings if validation failed
            if result.warnings:
                companies = Company.query.filter_by(user_id=current_user.id).order_by(Company.name).all()
                return render_template('add_transaction.html',
                                      companies=companies,
                                      warnings=result.warnings,
                                      show_warning=True,
                                      form_data=request.form)
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

    return render_template('add_transaction.html',
                          companies=companies,
                          warnings=warnings,
                          show_warning=False,
                          form_data=None,
                          existing_positions=existing_positions,
                          companies_with_research=companies_with_research,
                          preselected_company_id=preselected_company_id)

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
            try:
                transaction_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
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
        company_ticker = transaction.company.ticker_symbol

        # Delete transaction
        db.session.delete(transaction)
        db.session.commit()

        # Recalculate position for this company
        # Create a temporary transaction object to trigger recalculation
        temp_transaction = Transaction(
            user_id=current_user.id,
            company_id=company_id,
            type='BUY',  # Doesn't matter, just for recalculation
            date=now_utc().date(),
            quantity=0,
            price_per_share=0
        )
        update_portfolio_position(temp_transaction)

        flash(f'Transaction for {company_ticker} deleted successfully', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting transaction: {str(e)}', 'error')

    return redirect(url_for('portfolio.transactions'))

