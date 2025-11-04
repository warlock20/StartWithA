# app/portfolio/routes.py

from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import (
    Transaction, PortfolioPosition, Company, DecisionJournal,
    ResearchProject, DestinationCheckpoint, update_portfolio_position
)
from app.services.price_service import PriceService

# Import blueprint from current package (avoids circular import)
from . import portfolio_bp


@portfolio_bp.route('/')
@login_required
def dashboard():
    """Portfolio dashboard showing all positions and metrics"""
    # Get filter and sort parameters
    filter_status = request.args.get('filter_status', 'all')  # all, gains, losses
    sort_by = request.args.get('sort_by', 'company')  # company, value, gain_loss, percent, days
    sort_order = request.args.get('sort_order', 'asc')  # asc, desc

    # Get all active positions
    positions = PortfolioPosition.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).all()

    # Update prices if needed
    for position in positions:
        if PriceService.should_update_price(position):
            PriceService.update_position_price(position)

    # Apply filters
    if filter_status == 'gains':
        positions = [p for p in positions if p.unrealized_gain_loss and p.unrealized_gain_loss > 0]
    elif filter_status == 'losses':
        positions = [p for p in positions if p.unrealized_gain_loss and p.unrealized_gain_loss < 0]

    # Apply sorting
    reverse = (sort_order == 'desc')
    if sort_by == 'company':
        positions.sort(key=lambda p: p.company.ticker_symbol.lower(), reverse=reverse)
    elif sort_by == 'shares':
        positions.sort(key=lambda p: p.total_shares or 0, reverse=reverse)
    elif sort_by == 'value':
        positions.sort(key=lambda p: p.current_value or 0, reverse=reverse)
    elif sort_by == 'gain_loss':
        positions.sort(key=lambda p: p.unrealized_gain_loss or 0, reverse=reverse)
    elif sort_by == 'percent':
        positions.sort(key=lambda p: p.unrealized_gain_loss_pct or 0, reverse=reverse)
    elif sort_by == 'days':
        positions.sort(key=lambda p: p.days_held or 0, reverse=reverse)

    # Calculate portfolio totals
    portfolio_value = PriceService.get_portfolio_value(current_user.id)

    # Calculate gains and losses counts
    all_positions = PortfolioPosition.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).all()
    gains_count = sum(1 for p in all_positions if p.unrealized_gain_loss and p.unrealized_gain_loss > 0)
    losses_count = sum(1 for p in all_positions if p.unrealized_gain_loss and p.unrealized_gain_loss < 0)

    # Get recent transactions
    recent_transactions = Transaction.query.filter_by(
        user_id=current_user.id
    ).order_by(Transaction.date.desc()).limit(10).all()

    # Get upcoming checkpoints for portfolio companies
    # Get company IDs from active positions
    portfolio_company_ids = [pos.company_id for pos in all_positions]

    # Query upcoming checkpoints (Active status, future dates or recent past)
    today = date.today()
    upcoming_checkpoints = DestinationCheckpoint.query.filter(
        DestinationCheckpoint.user_id == current_user.id,
        DestinationCheckpoint.company_id.in_(portfolio_company_ids),
        DestinationCheckpoint.status == 'Active'
    ).order_by(DestinationCheckpoint.target_date.asc()).limit(5).all() if portfolio_company_ids else []

    return render_template('portfolio/dashboard.html',
                          positions=positions,
                          portfolio_value=portfolio_value,
                          recent_transactions=recent_transactions,
                          upcoming_checkpoints=upcoming_checkpoints,
                          today=today,
                          gains_count=gains_count,
                          losses_count=losses_count,
                          updated_time='just now',
                          filter_status=filter_status,
                          sort_by=sort_by,
                          sort_order=sort_order)


@portfolio_bp.route('/transactions')
@login_required
def transactions():
    """View all transactions with filtering"""
    # Get filter parameters
    company_id = request.args.get('company_id', type=int)
    transaction_type = request.args.get('type')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

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

    # Get transactions
    transactions = query.order_by(Transaction.date.desc()).all()

    # Get all companies for filter dropdown
    companies = Company.query.filter_by(user_id=current_user.id).order_by(Company.name).all()

    return render_template('portfolio/transactions.html',
                          transactions=transactions,
                          companies=companies)


@portfolio_bp.route('/transaction/new', methods=['GET', 'POST'])
@login_required
def add_transaction():
    """Add a new transaction"""
    if request.method == 'POST':
        try:
            # Get form data
            company_id = request.form.get('company_id', type=int)
            transaction_type = request.form.get('type')
            date_str = request.form.get('date')
            quantity = request.form.get('quantity', type=int)
            price_per_share = request.form.get('price_per_share')
            fees = request.form.get('fees', '0')
            notes = request.form.get('notes', '').strip()

            # Validation
            if not all([company_id, transaction_type, date_str, quantity, price_per_share]):
                flash('Please fill in all required fields', 'error')
                return redirect(url_for('portfolio.add_transaction'))

            # Validate company belongs to user
            company = Company.query.filter_by(id=company_id, user_id=current_user.id).first()
            if not company:
                flash('Invalid company selected', 'error')
                return redirect(url_for('portfolio.add_transaction'))

            # Parse date
            try:
                transaction_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid date format', 'error')
                return redirect(url_for('portfolio.add_transaction'))

            # Validate date not in future
            if transaction_date > datetime.now().date():
                flash('Transaction date cannot be in the future', 'error')
                return redirect(url_for('portfolio.add_transaction'))

            # Parse numeric values
            try:
                price_per_share = Decimal(price_per_share)
                fees = Decimal(fees) if fees else Decimal('0.00')
            except (InvalidOperation, ValueError):
                flash('Invalid price or fees amount', 'error')
                return redirect(url_for('portfolio.add_transaction'))

            # Validate quantity
            if quantity <= 0:
                flash('Quantity must be greater than zero', 'error')
                return redirect(url_for('portfolio.add_transaction'))

            # Validate price
            if price_per_share <= 0:
                flash('Price per share must be greater than zero', 'error')
                return redirect(url_for('portfolio.add_transaction'))

            # Additional validation for SELL transactions
            if transaction_type == 'SELL':
                # Check if user owns enough shares
                position = PortfolioPosition.query.filter_by(
                    user_id=current_user.id,
                    company_id=company_id
                ).first()

                if not position or position.total_shares < quantity:
                    owned_shares = position.total_shares if position else 0
                    flash(f'Cannot sell {quantity} shares. You only own {owned_shares} shares of {company.ticker_symbol}', 'error')
                    return redirect(url_for('portfolio.add_transaction'))

            # Check for research (for BUY transactions)
            bought_without_research = False
            reason_without_research = None

            if transaction_type == 'BUY':
                research_project = ResearchProject.query.filter_by(
                    company_id=company_id,
                    user_id=current_user.id
                ).first()

                if not research_project:
                    # No research found - warning flow
                    bought_without_research = True
                    reason_without_research = request.form.get('reason_without_research', '').strip()

                    if not reason_without_research:
                        flash('Please provide a reason for buying without research', 'warning')
                        # Redirect back with form data preserved
                        return render_template('portfolio/add_transaction.html',
                                             companies=Company.query.filter_by(user_id=current_user.id).order_by(Company.name).all(),
                                             show_warning=True,
                                             form_data=request.form)

            # Create transaction
            transaction = Transaction(
                user_id=current_user.id,
                company_id=company_id,
                type=transaction_type,
                date=transaction_date,
                quantity=quantity,
                price_per_share=price_per_share,
                fees=fees,
                notes=notes,
                bought_without_research=bought_without_research,
                reason_without_research=reason_without_research
            )

            db.session.add(transaction)
            db.session.flush()  # Get transaction ID

            # Update portfolio position
            update_portfolio_position(transaction)

            # Create Decision Journal entry for BUY transactions (if research exists)
            if transaction_type == 'BUY' and not bought_without_research:
                research_project = ResearchProject.query.filter_by(
                    company_id=company_id,
                    user_id=current_user.id
                ).first()

                if research_project:
                    # Check if decision journal already exists
                    existing_journal = DecisionJournal.query.filter_by(
                        company_id=company_id,
                        user_id=current_user.id,
                        decision_type='BUY'
                    ).first()

                    if not existing_journal:
                        # Create new decision journal
                        decision_journal = DecisionJournal(
                            user_id=current_user.id,
                            company_id=company_id,
                            decision_type='BUY',
                            decision_date=transaction_date,
                            investment_thesis=research_project.summary or 'Investment thesis from research',
                            is_portfolio_decision=True,
                            linked_research_id=research_project.id
                        )
                        db.session.add(decision_journal)
                        db.session.flush()

                        # Link transaction to decision journal
                        transaction.decision_journal_id = decision_journal.id

            db.session.commit()

            flash(f'{transaction_type} transaction for {company.ticker_symbol} recorded successfully', 'success')

            # Redirect based on transaction type
            if transaction_type == 'BUY' and transaction.decision_journal_id:
                flash('Please review and complete your decision journal', 'info')
                return redirect(url_for('analytics.edit_decision_journal', id=transaction.decision_journal_id))
            elif transaction_type == 'SELL':
                flash('Please complete your post-mortem analysis', 'info')
                # For now, redirect to dashboard. We'll add post-mortem prompt later
                return redirect(url_for('portfolio.dashboard'))
            else:
                return redirect(url_for('portfolio.dashboard'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error adding transaction: {str(e)}', 'error')
            return redirect(url_for('portfolio.add_transaction'))

    # GET request - show form
    companies = Company.query.filter_by(user_id=current_user.id).order_by(Company.name).all()
    return render_template('portfolio/add_transaction.html',
                          companies=companies,
                          show_warning=False,
                          form_data=None)


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
    return render_template('portfolio/edit_transaction.html', transaction=transaction)


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
            date=datetime.now().date(),
            quantity=0,
            price_per_share=0
        )
        update_portfolio_position(temp_transaction)

        flash(f'Transaction for {company_ticker} deleted successfully', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting transaction: {str(e)}', 'error')

    return redirect(url_for('portfolio.transactions'))


@portfolio_bp.route('/position/<int:company_id>')
@login_required
def position_detail(company_id):
    """View detailed position information for a company"""
    # Get company
    company = Company.query.filter_by(
        id=company_id,
        user_id=current_user.id
    ).first_or_404()

    # Get position
    position = PortfolioPosition.query.filter_by(
        user_id=current_user.id,
        company_id=company_id
    ).first()

    if not position:
        flash('No position found for this company', 'warning')
        return redirect(url_for('portfolio.dashboard'))

    # Update price if needed
    if PriceService.should_update_price(position):
        PriceService.update_position_price(position)

    # Get all transactions for this position
    transactions = Transaction.query.filter_by(
        user_id=current_user.id,
        company_id=company_id
    ).order_by(Transaction.date.desc()).all()

    # Get linked decision journal
    decision_journal = DecisionJournal.query.filter_by(
        user_id=current_user.id,
        company_id=company_id,
        is_portfolio_decision=True
    ).first()

    # Get destination checkpoints
    checkpoints = company.destination_checkpoints.filter_by(
        user_id=current_user.id
    ).order_by(db.desc('target_date')).all()

    # Get research project
    research_project = ResearchProject.query.filter_by(
        company_id=company_id,
        user_id=current_user.id
    ).first()

    return render_template('portfolio/position_detail.html',
                          company=company,
                          position=position,
                          transactions=transactions,
                          decision_journal=decision_journal,
                          checkpoints=checkpoints,
                          research_project=research_project,
                          today=date.today)


@portfolio_bp.route('/refresh-prices', methods=['POST'])
@login_required
def refresh_prices():
    """Manually refresh all portfolio prices"""
    try:
        results = PriceService.update_all_positions_batch(current_user.id, force=True)

        if results['updated'] > 0:
            flash(f"Successfully updated {results['updated']} positions", 'success')

        if results['failed'] > 0:
            flash(f"Failed to update {results['failed']} positions: {', '.join(results['errors'])}", 'warning')

    except Exception as e:
        flash(f'Error refreshing prices: {str(e)}', 'error')

    return redirect(url_for('portfolio.dashboard'))


@portfolio_bp.route('/api/company-search')
@login_required
def company_search():
    """API endpoint for company autocomplete search"""
    query = request.args.get('q', '').strip()

    if not query or len(query) < 2:
        return jsonify([])

    companies = Company.query.filter(
        Company.user_id == current_user.id,
        db.or_(
            Company.name.ilike(f'%{query}%'),
            Company.ticker_symbol.ilike(f'%{query}%')
        )
    ).order_by(Company.name).limit(10).all()

    results = [{
        'id': c.id,
        'name': c.name,
        'ticker': c.ticker_symbol,
        'label': f'{c.ticker_symbol} - {c.name}'
    } for c in companies]

    return jsonify(results)


@portfolio_bp.route('/checkpoint/<int:checkpoint_id>/update-status', methods=['POST'])
@login_required
def update_checkpoint_status(checkpoint_id):
    """Update the status of a destination checkpoint"""
    try:
        data = request.get_json()
        new_status = data.get('status')

        # Validate status
        if new_status not in ['Active', 'Met', 'Not Met']:
            return jsonify({'success': False, 'error': 'Invalid status'}), 400

        # Get checkpoint and verify ownership
        checkpoint = DestinationCheckpoint.query.filter_by(
            id=checkpoint_id,
            user_id=current_user.id
        ).first()

        if not checkpoint:
            return jsonify({'success': False, 'error': 'Checkpoint not found'}), 404

        # Update status
        checkpoint.status = new_status
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Checkpoint marked as {new_status}'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
