# app/portfolio/routes.py

from datetime import datetime, date, timedelta
from decimal import Decimal, InvalidOperation
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func, extract
from app import db
from app.models import (
    Transaction, PortfolioPosition, Company, DecisionJournal,
    ResearchProject, DestinationCheckpoint, ThesisEvolution, update_portfolio_position
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

            if transaction_type == 'BUY':
                research_project = ResearchProject.query.filter_by(
                    company_id=company_id,
                    user_id=current_user.id
                ).first()

                if not research_project:
                    # No research found - require Decision Journal
                    bought_without_research = True
                    investment_thesis = request.form.get('investment_thesis', '').strip()

                    # Validate thesis is provided and meets minimum word count
                    if not investment_thesis:
                        flash('Please provide your investment thesis for buying without research', 'warning')
                        return render_template('portfolio/add_transaction.html',
                                             companies=Company.query.filter_by(user_id=current_user.id).order_by(Company.name).all(),
                                             show_warning=True,
                                             form_data=request.form)

                    # Check word count (minimum 20 words)
                    word_count = len(investment_thesis.split())
                    if word_count < 20:
                        flash(f'Investment thesis must be at least 20 words (you provided {word_count})', 'warning')
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
                bought_without_research=bought_without_research
            )

            db.session.add(transaction)
            db.session.flush()  # Get transaction ID

            # Update portfolio position
            update_portfolio_position(transaction)

            # Create Decision Journal entry for BUY and SELL transactions
            decision_journal = None
            if transaction_type == 'BUY':
                # Check if decision journal already exists for this company
                existing_journal = DecisionJournal.query.filter_by(
                    company_id=company_id,
                    user_id=current_user.id,
                    decision_type='BUY',
                    is_portfolio_decision=True
                ).first()

                if not existing_journal:
                    if bought_without_research:
                        # Create Decision Journal from form data
                        investment_thesis = request.form.get('investment_thesis', '').strip()
                        non_research_source = request.form.get('non_research_source', '').strip()
                        confidence_score = request.form.get('confidence_score', type=int)
                        expected_return = request.form.get('expected_return', type=float)
                        expected_timeframe = request.form.get('expected_timeframe', type=int)

                        word_count = len(investment_thesis.split())
                        thesis_depth = 'comprehensive' if word_count > 100 else ('brief' if word_count >= 50 else 'minimal')

                        decision_journal = DecisionJournal(
                            user_id=current_user.id,
                            company_id=company_id,
                            decision_type='BUY',
                            decision_date=transaction_date,
                            investment_thesis=investment_thesis,
                            confidence_score=confidence_score,
                            expected_return=expected_return,
                            expected_timeframe=expected_timeframe,
                            is_portfolio_decision=True,
                            thesis_depth=thesis_depth,
                            thesis_word_count=word_count,
                            non_research_source=non_research_source
                        )
                    else:
                        # Create Decision Journal from research project
                        research_project = ResearchProject.query.filter_by(
                            company_id=company_id,
                            user_id=current_user.id
                        ).first()

                        if research_project:
                            decision_journal = DecisionJournal(
                                user_id=current_user.id,
                                company_id=company_id,
                                decision_type='BUY',
                                decision_date=transaction_date,
                                investment_thesis=research_project.summary or 'Investment thesis from research',
                                is_portfolio_decision=True,
                                linked_research_id=research_project.id,
                                thesis_depth='comprehensive'
                            )

                    if decision_journal:
                        db.session.add(decision_journal)
                        db.session.flush()
                        # Link transaction to decision journal
                        transaction.decision_journal_id = decision_journal.id

            elif transaction_type == 'SELL':
                # Create SELL Decision Journal entry
                # Get the original BUY decision journal if it exists
                buy_journal = DecisionJournal.query.filter_by(
                    company_id=company_id,
                    user_id=current_user.id,
                    decision_type='BUY',
                    is_portfolio_decision=True
                ).first()

                # Create SELL decision journal
                sell_journal = DecisionJournal(
                    user_id=current_user.id,
                    company_id=company_id,
                    decision_type='SELL',
                    decision_date=transaction_date,
                    investment_thesis=f'Selling {quantity} shares at ${price_per_share}',
                    is_portfolio_decision=True
                )

                db.session.add(sell_journal)
                db.session.flush()

                # Link transaction to decision journal
                transaction.decision_journal_id = sell_journal.id

            db.session.commit()

            flash(f'{transaction_type} transaction for {company.ticker_symbol} recorded successfully', 'success')

            # Redirect based on transaction type
            if transaction_type == 'SELL' and sell_journal:
                flash('Please complete a post-mortem analysis for this sale', 'info')
                # Redirect to post-mortem form
                return redirect(url_for('portfolio.sell_postmortem', journal_id=sell_journal.id))
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


@portfolio_bp.route('/decision-journal')
@login_required
def decision_journal_list():
    """List all portfolio decision journals"""
    # Get all portfolio decision journals
    journals = DecisionJournal.query.filter_by(
        user_id=current_user.id,
        is_portfolio_decision=True
    ).order_by(DecisionJournal.decision_date.desc()).all()

    # Calculate statistics
    total_decisions = len(journals)
    buy_decisions = sum(1 for j in journals if j.decision_type == 'BUY')

    # Count non-research purchases
    non_research_purchases = sum(1 for j in journals if j.non_research_source is not None)

    # Calculate average confidence
    journals_with_confidence = [j for j in journals if j.confidence_score is not None]
    avg_confidence = sum(j.confidence_score for j in journals_with_confidence) / len(journals_with_confidence) if journals_with_confidence else 0

    # Track outcomes (for completed positions)
    journals_with_outcomes = [j for j in journals if j.actual_return is not None]
    successful_trades = sum(1 for j in journals_with_outcomes if j.actual_return > 0)
    win_rate = (successful_trades / len(journals_with_outcomes) * 100) if journals_with_outcomes else 0

    return render_template('portfolio/decision_journal_list.html',
                          journals=journals,
                          total_decisions=total_decisions,
                          buy_decisions=buy_decisions,
                          non_research_purchases=non_research_purchases,
                          avg_confidence=round(avg_confidence, 1),
                          win_rate=round(win_rate, 1))


@portfolio_bp.route('/decision-journal/<int:journal_id>')
@login_required
def view_decision_journal(journal_id):
    """View a single decision journal entry"""
    journal = DecisionJournal.query.filter_by(
        id=journal_id,
        user_id=current_user.id
    ).first_or_404()

    # Get associated transactions
    transactions = Transaction.query.filter_by(
        user_id=current_user.id,
        company_id=journal.company_id,
        decision_journal_id=journal_id
    ).order_by(Transaction.date).all()

    # Get portfolio position
    position = PortfolioPosition.query.filter_by(
        user_id=current_user.id,
        company_id=journal.company_id
    ).first()

    # Get research project if exists
    research_project = None
    if journal.linked_research_id:
        research_project = ResearchProject.query.get(journal.linked_research_id)

    return render_template('portfolio/decision_journal_detail.html',
                          journal=journal,
                          transactions=transactions,
                          position=position,
                          research_project=research_project)


@portfolio_bp.route('/sell-postmortem/<int:journal_id>', methods=['GET', 'POST'])
@login_required
def sell_postmortem(journal_id):
    """Complete post-mortem analysis after selling"""
    journal = DecisionJournal.query.filter_by(
        id=journal_id,
        user_id=current_user.id,
        decision_type='SELL'
    ).first_or_404()

    # Get the original BUY journal
    buy_journal = DecisionJournal.query.filter_by(
        company_id=journal.company_id,
        user_id=current_user.id,
        decision_type='BUY',
        is_portfolio_decision=True
    ).first()

    if request.method == 'POST':
        # Get form data
        sell_reason = request.form.get('sell_reason', '').strip()
        actual_return = request.form.get('actual_return', type=float)
        what_went_right = request.form.get('what_went_right', '').strip()
        what_went_wrong = request.form.get('what_went_wrong', '').strip()
        lessons_learned = request.form.get('lessons_learned', '').strip()
        would_repeat = request.form.get('would_repeat') == 'true'
        mistake_category = request.form.get('mistake_category', '').strip()
        success_category = request.form.get('success_category', '').strip()

        # Update SELL journal with exit reasoning
        journal.investment_thesis = sell_reason if sell_reason else journal.investment_thesis

        # Update BUY journal with post-mortem data if it exists
        if buy_journal:
            buy_journal.actual_return = actual_return
            buy_journal.outcome_date = journal.decision_date
            buy_journal.what_went_right = what_went_right
            buy_journal.what_went_wrong = what_went_wrong
            buy_journal.lessons_learned = lessons_learned
            buy_journal.would_repeat = would_repeat
            buy_journal.mistake_category = mistake_category if actual_return and actual_return < 0 else None
            buy_journal.success_category = success_category if actual_return and actual_return > 0 else None
            buy_journal.updated_at = now_utc()

        try:
            db.session.commit()
            flash('Post-mortem analysis saved successfully', 'success')
            return redirect(url_for('portfolio.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving post-mortem: {str(e)}', 'error')

    return render_template('portfolio/sell_postmortem.html',
                          journal=journal,
                          buy_journal=buy_journal)


@portfolio_bp.route('/position/<int:company_id>/journey')
@login_required
def investment_journey(company_id):
    """
    Unified investment journey timeline showing thesis evolution,
    destination checkpoints, and market events chronologically.
    """
    # Get company and verify ownership
    company = Company.query.filter_by(
        id=company_id,
        user_id=current_user.id
    ).first_or_404()

    # Get portfolio position
    position = PortfolioPosition.query.filter_by(
        user_id=current_user.id,
        company_id=company_id
    ).first()

    # Get all thesis versions
    thesis_versions = ThesisEvolution.query.filter_by(
        company_id=company_id,
        user_id=current_user.id
    ).order_by(ThesisEvolution.created_at).all()

    # Get all destination checkpoints
    checkpoints = DestinationCheckpoint.query.filter_by(
        company_id=company_id,
        user_id=current_user.id
    ).order_by(DestinationCheckpoint.target_date).all()

    # Get all transactions (for market events)
    transactions = Transaction.query.filter_by(
        company_id=company_id,
        user_id=current_user.id
    ).order_by(Transaction.date).all()

    # Get decision journals
    decision_journals = DecisionJournal.query.filter_by(
        company_id=company_id,
        user_id=current_user.id,
        is_portfolio_decision=True
    ).order_by(DecisionJournal.decision_date).all()

    # Combine all events into unified timeline
    timeline_events = []

    # Add thesis versions
    for thesis in thesis_versions:
        timeline_events.append({
            'type': 'thesis',
            'date': thesis.created_at.date() if thesis.created_at else date.today(),
            'datetime': thesis.created_at,
            'data': thesis
        })

    # Add checkpoints
    for checkpoint in checkpoints:
        timeline_events.append({
            'type': 'checkpoint',
            'date': checkpoint.target_date,
            'datetime': datetime.combine(checkpoint.target_date, datetime.min.time()),
            'data': checkpoint
        })

    # Add significant transactions as events
    for txn in transactions:
        if txn.type in ['BUY', 'SELL']:  # Only show BUY/SELL, not dividends
            timeline_events.append({
                'type': 'transaction',
                'date': txn.date,
                'datetime': datetime.combine(txn.date, datetime.min.time()),
                'data': txn
            })

    # Sort timeline by datetime (most recent first for display)
    timeline_events.sort(key=lambda x: x['datetime'], reverse=True)

    # Calculate journey statistics
    total_return = 0
    if position and position.unrealized_gain_loss_pct:
        total_return = position.unrealized_gain_loss_pct

    checkpoints_met = sum(1 for cp in checkpoints if cp.status == 'Met')
    total_checkpoints = len(checkpoints)

    days_held = 0
    if position and position.days_held:
        days_held = position.days_held

    current_conviction = 0
    if thesis_versions:
        latest_thesis = max(thesis_versions, key=lambda x: x.created_at or datetime.min)
        current_conviction = latest_thesis.conviction_level or 0

    journey_stats = {
        'total_return': total_return,
        'thesis_updates': len(thesis_versions),
        'checkpoints_met': checkpoints_met,
        'total_checkpoints': total_checkpoints,
        'days_held': days_held,
        'current_conviction': current_conviction
    }

    # Identify current thesis
    current_thesis = None
    if thesis_versions:
        current_thesis_objs = [t for t in thesis_versions if t.is_current]
        if current_thesis_objs:
            current_thesis = current_thesis_objs[0]
        else:
            # Fallback to most recent
            current_thesis = max(thesis_versions, key=lambda x: x.created_at or datetime.min)

    return render_template('portfolio/investment_journey.html',
                          company=company,
                          position=position,
                          timeline_events=timeline_events,
                          journey_stats=journey_stats,
                          current_thesis=current_thesis,
                          thesis_count=len(thesis_versions),
                          checkpoint_count=len(checkpoints),
                          event_count=len([e for e in timeline_events if e['type'] == 'transaction']))


@portfolio_bp.route('/position/<int:company_id>/thesis/new', methods=['GET', 'POST'])
@login_required
def add_thesis_version(company_id):
    """Add a new thesis version for a company"""
    # Get company and verify ownership
    company = Company.query.filter_by(
        id=company_id,
        user_id=current_user.id
    ).first_or_404()

    # Get position for context
    position = PortfolioPosition.query.filter_by(
        user_id=current_user.id,
        company_id=company_id
    ).first()

    if request.method == 'POST':
        try:
            # Get form data
            thesis = request.form.get('thesis', '').strip()
            change_summary = request.form.get('change_summary', '').strip()
            change_trigger = request.form.get('change_trigger', '').strip()
            conviction_level = request.form.get('conviction_level', type=int)
            position_sizing = request.form.get('position_sizing', '').strip()

            # Validation
            if not thesis:
                flash('Please provide your investment thesis', 'error')
                return redirect(url_for('portfolio.add_thesis_version', company_id=company_id))

            if not change_summary:
                flash('Please provide a summary of what changed', 'error')
                return redirect(url_for('portfolio.add_thesis_version', company_id=company_id))

            if not conviction_level or conviction_level < 1 or conviction_level > 10:
                flash('Conviction level must be between 1 and 10', 'error')
                return redirect(url_for('portfolio.add_thesis_version', company_id=company_id))

            # Get bull case points (dynamically - check all possible indices)
            bull_case = []
            i = 1
            while True:
                point = request.form.get(f'bull_case_{i}', '').strip()
                if not point and i > 20:  # Safety limit to prevent infinite loop
                    break
                if point:
                    bull_case.append(point)
                i += 1

            # Get bear case points (dynamically)
            bear_case = []
            i = 1
            while True:
                point = request.form.get(f'bear_case_{i}', '').strip()
                if not point and i > 20:  # Safety limit
                    break
                if point:
                    bear_case.append(point)
                i += 1

            # Get key metrics
            target_price = request.form.get('target_price', type=float)
            key_metrics = {}
            if target_price:
                key_metrics['target_price'] = target_price

            # Get next version number
            max_version = db.session.query(db.func.max(ThesisEvolution.version)).filter_by(
                user_id=current_user.id,
                company_id=company_id
            ).scalar() or 0
            next_version = max_version + 1

            # Mark all previous versions as not current
            ThesisEvolution.query.filter_by(
                user_id=current_user.id,
                company_id=company_id,
                is_current=True
            ).update({'is_current': False})

            # Create new thesis version
            thesis_version = ThesisEvolution(
                user_id=current_user.id,
                company_id=company_id,
                version=next_version,
                thesis=thesis,
                change_summary=change_summary,
                change_trigger=change_trigger if change_trigger else None,
                conviction_level=conviction_level,
                position_sizing=position_sizing if position_sizing else None,
                bull_case=bull_case if bull_case else None,
                bear_case=bear_case if bear_case else None,
                key_metrics=key_metrics if key_metrics else None,
                is_current=True
            )

            db.session.add(thesis_version)
            db.session.commit()

            flash(f'Thesis Version {next_version} created successfully', 'success')
            return redirect(url_for('portfolio.investment_journey', company_id=company_id))

        except Exception as e:
            db.session.rollback()
            flash(f'Error creating thesis version: {str(e)}', 'error')
            return redirect(url_for('portfolio.add_thesis_version', company_id=company_id))

    # GET request - show form
    # Get current thesis for reference
    current_thesis = ThesisEvolution.query.filter_by(
        user_id=current_user.id,
        company_id=company_id,
        is_current=True
    ).first()

    # Get version number
    max_version = db.session.query(db.func.max(ThesisEvolution.version)).filter_by(
        user_id=current_user.id,
        company_id=company_id
    ).scalar() or 0
    next_version = max_version + 1

    return render_template('portfolio/add_thesis_version.html',
                          company=company,
                          position=position,
                          current_thesis=current_thesis,
                          next_version=next_version)


@portfolio_bp.route('/analytics')
@login_required
def analytics():
    """
    Portfolio Analytics - Performance Overview
    Quick metrics and returns focus
    """
    # Get all active positions
    positions = PortfolioPosition.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).all()

    # Update prices if needed
    for position in positions:
        if PriceService.should_update_price(position):
            PriceService.update_position_price(position)

    # Calculate portfolio totals
    portfolio_value = PriceService.get_portfolio_value(current_user.id)

    # Calculate total return
    total_return = portfolio_value['total_unrealized_gain_loss']
    total_return_pct = portfolio_value['total_unrealized_gain_loss_pct']

    # Calculate annualized return
    earliest_date = db.session.query(func.min(PortfolioPosition.first_purchase_date)).filter_by(
        user_id=current_user.id,
        is_active=True
    ).scalar()

    annualized_return = Decimal('0.00')
    years_held = 0
    if earliest_date and portfolio_value['total_cost'] > 0:
        days_held = (date.today() - earliest_date).days
        if days_held > 0:
            years_held = days_held / 365.25
            if total_return_pct:
                total_return_decimal = float(total_return_pct) / 100
                annualized_return = ((1 + total_return_decimal) ** (1 / years_held) - 1) * 100

    # Calculate win rate
    winning_positions = sum(1 for p in positions if p.unrealized_gain_loss and p.unrealized_gain_loss > 0)
    total_positions = len(positions)
    win_rate = (winning_positions / total_positions * 100) if total_positions > 0 else 0

    # Calculate average holding period
    avg_hold_days = 0
    if positions:
        total_days = sum(p.days_held for p in positions if p.days_held)
        avg_hold_days = total_days / len(positions) if len(positions) > 0 else 0

    # Get top performers (top 5)
    top_performers = sorted(
        [p for p in positions if p.unrealized_gain_loss_pct],
        key=lambda p: p.unrealized_gain_loss_pct,
        reverse=True
    )[:5]

    # Get bottom performers (bottom 5)
    bottom_performers = sorted(
        [p for p in positions if p.unrealized_gain_loss_pct],
        key=lambda p: p.unrealized_gain_loss_pct
    )[:5]

    # Calculate monthly performance (last 12 months)
    monthly_performance = []
    for i in range(11, -1, -1):
        month_date = date.today() - timedelta(days=i*30)
        month_name = month_date.strftime('%B %Y')

        # Get transactions for this month
        month_start = date(month_date.year, month_date.month, 1)
        if month_date.month == 12:
            month_end = date(month_date.year + 1, 1, 1)
        else:
            month_end = date(month_date.year, month_date.month + 1, 1)

        month_transactions = Transaction.query.filter(
            Transaction.user_id == current_user.id,
            Transaction.date >= month_start,
            Transaction.date < month_end
        ).count()

        monthly_performance.append({
            'month': month_name,
            'month_short': month_date.strftime('%b'),
            'trades': month_transactions
        })

    # Generate chart data for portfolio value over time
    chart_labels = [m['month_short'] for m in monthly_performance]

    # Calculate historical values (simplified projection based on current data)
    current_value = float(portfolio_value['total_value'])
    cost_basis = float(portfolio_value['total_cost'])

    chart_values = []
    if len(chart_labels) > 0:
        growth_per_month = (current_value - cost_basis) / len(chart_labels) if len(chart_labels) > 0 else 0
        for i in range(len(chart_labels)):
            value = cost_basis + (growth_per_month * (i + 1))
            chart_values.append(round(value, 2))

    return render_template('portfolio/analytics.html',
                          portfolio_value=portfolio_value,
                          total_return=total_return,
                          total_return_pct=total_return_pct,
                          annualized_return=annualized_return,
                          win_rate=win_rate,
                          winning_positions=winning_positions,
                          total_positions=total_positions,
                          avg_hold_days=avg_hold_days,
                          top_performers=top_performers,
                          bottom_performers=bottom_performers,
                          monthly_performance=monthly_performance,
                          chart_labels=chart_labels,
                          chart_values=chart_values,
                          cost_basis=cost_basis)


@portfolio_bp.route('/analytics/decisions')
@login_required
def analytics_decisions():
    """
    Decision Intelligence Dashboard
    Deep behavioral analysis and learning from patterns
    """
    # Get all positions (both active and closed)
    all_positions = PortfolioPosition.query.filter_by(
        user_id=current_user.id
    ).all()

    # Get all decision journals
    all_journals = DecisionJournal.query.filter_by(
        user_id=current_user.id,
        is_portfolio_decision=True
    ).all()

    # Calculate research-backed vs non-research statistics
    research_backed = [j for j in all_journals if j.linked_research_id is not None and j.decision_type == 'BUY']
    non_research = [j for j in all_journals if j.non_research_source is not None and j.decision_type == 'BUY']

    # Calculate average returns for each category
    research_positions = []
    non_research_positions = []

    for journal in research_backed:
        position = next((p for p in all_positions if p.company_id == journal.company_id), None)
        if position and position.unrealized_gain_loss_pct:
            research_positions.append(position)

    for journal in non_research:
        position = next((p for p in all_positions if p.company_id == journal.company_id), None)
        if position and position.unrealized_gain_loss_pct:
            non_research_positions.append(position)

    # Calculate stats
    research_avg_return = sum(float(p.unrealized_gain_loss_pct) for p in research_positions) / len(research_positions) if research_positions else 0
    research_win_rate = sum(1 for p in research_positions if p.unrealized_gain_loss and p.unrealized_gain_loss > 0) / len(research_positions) * 100 if research_positions else 0
    research_avg_hold = sum(p.days_held for p in research_positions) / len(research_positions) if research_positions else 0

    non_research_avg_return = sum(float(p.unrealized_gain_loss_pct) for p in non_research_positions) / len(non_research_positions) if non_research_positions else 0
    non_research_win_rate = sum(1 for p in non_research_positions if p.unrealized_gain_loss and p.unrealized_gain_loss > 0) / len(non_research_positions) * 100 if non_research_positions else 0
    non_research_avg_hold = sum(p.days_held for p in non_research_positions) / len(non_research_positions) if non_research_positions else 0

    # Get active positions for current analysis
    active_positions = [p for p in all_positions if p.is_active]

    # Calculate holding period performance buckets
    hold_period_buckets = {
        '0-30': [],
        '31-90': [],
        '91-180': [],
        '181-365': [],
        '365+': []
    }

    for position in active_positions:
        if position.unrealized_gain_loss_pct:
            days = position.days_held
            if days <= 30:
                hold_period_buckets['0-30'].append(float(position.unrealized_gain_loss_pct))
            elif days <= 90:
                hold_period_buckets['31-90'].append(float(position.unrealized_gain_loss_pct))
            elif days <= 180:
                hold_period_buckets['91-180'].append(float(position.unrealized_gain_loss_pct))
            elif days <= 365:
                hold_period_buckets['181-365'].append(float(position.unrealized_gain_loss_pct))
            else:
                hold_period_buckets['365+'].append(float(position.unrealized_gain_loss_pct))

    # Calculate averages for each bucket
    hold_period_stats = {}
    for period, returns in hold_period_buckets.items():
        avg = sum(returns) / len(returns) if returns else 0
        hold_period_stats[period] = round(avg, 1)

    # Decision Quality Matrix
    # Good Process = Research-backed, Bad Process = No research
    good_process_good_outcome = sum(1 for p in research_positions if p.unrealized_gain_loss and p.unrealized_gain_loss > 0)
    good_process_bad_outcome = sum(1 for p in research_positions if p.unrealized_gain_loss and p.unrealized_gain_loss <= 0)
    bad_process_good_outcome = sum(1 for p in non_research_positions if p.unrealized_gain_loss and p.unrealized_gain_loss > 0)
    bad_process_bad_outcome = sum(1 for p in non_research_positions if p.unrealized_gain_loss and p.unrealized_gain_loss <= 0)

    # Recent decisions (last 10)
    recent_decisions = Transaction.query.filter_by(
        user_id=current_user.id
    ).filter(
        Transaction.type.in_(['BUY', 'SELL'])
    ).order_by(Transaction.date.desc()).limit(10).all()

    return render_template('portfolio/analytics_decisions.html',
                          research_backed_count=len(research_positions),
                          non_research_count=len(non_research_positions),
                          research_avg_return=research_avg_return,
                          research_win_rate=research_win_rate,
                          research_avg_hold=research_avg_hold,
                          non_research_avg_return=non_research_avg_return,
                          non_research_win_rate=non_research_win_rate,
                          non_research_avg_hold=non_research_avg_hold,
                          hold_period_stats=hold_period_stats,
                          good_process_good_outcome=good_process_good_outcome,
                          good_process_bad_outcome=good_process_bad_outcome,
                          bad_process_good_outcome=bad_process_good_outcome,
                          bad_process_bad_outcome=bad_process_bad_outcome,
                          recent_decisions=recent_decisions)
