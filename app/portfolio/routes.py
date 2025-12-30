# app/portfolio/routes.py

import logging
from datetime import datetime, date, timedelta
from decimal import Decimal, InvalidOperation
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from app import db

# Configure logger
logger = logging.getLogger(__name__)
from app.models import (
    Transaction, PortfolioPosition, Company, DecisionJournal,
    ResearchProject, DestinationCheckpoint, ThesisEvolution, update_portfolio_position, ResearchOutcome
)
from app.services.currency_service import CurrencyService
from app.services.price_service import PriceService
from app.services.too_hard_service import TooHardBasketService
from app.utils.time_utils import now_utc
from app.utils.financial_utils import calculate_cagr
from app.utils.portfolio_utils import (
    calculate_win_rate, calculate_average_return, filter_positions_by_performance,
    calculate_average_holding_period, calculate_holding_period_stats,
    calculate_confidence_stats, count_positions_by_status,
    get_top_performers, get_bottom_performers
)
from app.services.intelligence_engine import check_sell_warnings

from app.constants import (
    TRANSACTIONS_PER_PAGE, JOURNALS_PER_PAGE, MIN_TRADES_FOR_INSIGHTS,
    DEFAULT_TOP_PERFORMERS_LIMIT, DEFAULT_BOTTOM_PERFORMERS_LIMIT,
    RECENT_TRANSACTIONS_LIMIT, RECENT_DECISIONS_LIMIT, UPCOMING_CHECKPOINTS_LIMIT,
    DEFAULT_CHECKPOINT_LOOKBACK_DAYS, MONTHLY_PERFORMANCE_MONTHS,
    MAX_DYNAMIC_FORM_FIELDS,
    GRADE_A_THRESHOLD, GRADE_B_THRESHOLD, GRADE_C_THRESHOLD, GRADE_D_THRESHOLD
)
from app.services.portfolio_intelligence import (
    get_upcoming_checkpoints, get_thesis_reality_check, PortfolioIntelligenceService,
    get_learning_insights, get_correlation_data
    )
from app.services.intelligence_engine import IntelligenceEngine, get_portfolio_warnings
from app.services.transaction_service import TransactionService

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

    # Get all active positions with eager loading (unfiltered for stats)
    all_positions = PortfolioPosition.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).options(
        joinedload(PortfolioPosition.company).joinedload(Company.sector)
    ).all()

    # Update prices if needed
    for position in all_positions:
        if PriceService.should_update_price(position):
            PriceService.update_position_price(position)

    # Apply filters for display (keep all_positions unfiltered for stats)
    positions = filter_positions_by_performance(all_positions, filter_status)

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

    # Calculate gains and losses counts using utility
    status_counts = count_positions_by_status(all_positions)
    gains_count = status_counts['winning']
    losses_count = status_counts['losing']

    # Get recent transactions
    recent_transactions = Transaction.query.filter_by(
        user_id=current_user.id
    ).order_by(Transaction.date.desc()).limit(RECENT_TRANSACTIONS_LIMIT).all()

    # Get upcoming checkpoints for portfolio companies
    # Get company IDs from active positions
    portfolio_company_ids = [pos.company_id for pos in all_positions]

    # Query upcoming checkpoints (Active status, future dates or recent past)
    today = now_utc().date()
    upcoming_checkpoints = DestinationCheckpoint.query.filter(
        DestinationCheckpoint.user_id == current_user.id,
        DestinationCheckpoint.company_id.in_(portfolio_company_ids),
        DestinationCheckpoint.status == 'Active'
    ).order_by(DestinationCheckpoint.target_date.asc()).limit(UPCOMING_CHECKPOINTS_LIMIT).all() if portfolio_company_ids else []

    # Calculate Too Hard Basket rate (research discipline metric)
    too_hard_items = TooHardBasketService.get_all_too_hard_companies(user_id=current_user.id)
    total_researched = ResearchProject.query.filter_by(user_id=current_user.id).count()
    too_hard_rate = (len(too_hard_items) / total_researched * 100) if total_researched > 0 else 0

    # Calculate inbox count (incomplete research projects)
    inbox_count = ResearchProject.query.filter_by(
        user_id=current_user.id,
        status='in_progress'
    ).count()

    # Calculate portfolio count (number of active positions)
    portfolio_count = len(all_positions)

    # Get user currency settings
    user_currency = current_user.base_currency
    currency_symbol = CurrencyService.get_currency_symbol(user_currency)

    intelligence_service = PortfolioIntelligenceService(current_user.id)
    checkpoint_summary = intelligence_service.get_checkpoint_summary()
    checkpoints_preview = intelligence_service.get_upcoming_checkpoints(days_ahead=DEFAULT_CHECKPOINT_LOOKBACK_DAYS)
    
    return render_template('portfolio_dashboard.html',
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
                          sort_order=sort_order,
                          user_currency=user_currency,
                          currency_symbol=currency_symbol,
                          too_hard_rate=too_hard_rate,
                          inbox_count=inbox_count,
                          portfolio_count=portfolio_count,
                          checkpoint_summary = checkpoint_summary,
                          checkpoints_preview = checkpoints_preview)


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

    # Get all transactions for this position with eager loading
    transactions = Transaction.query.filter_by(
        user_id=current_user.id,
        company_id=company_id
    ).options(
        joinedload(Transaction.company)
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

    # Get user currency settings
    user_currency = current_user.base_currency
    currency_symbol = CurrencyService.get_currency_symbol(user_currency)

    return render_template('position_detail.html',
                          company=company,
                          position=position,
                          transactions=transactions,
                          decision_journal=decision_journal,
                          checkpoints=checkpoints,
                          research_project=research_project,
                          user_currency=user_currency,
                          currency_symbol=currency_symbol,
                          today=now_utc().date())


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
    """List all portfolio decision journals with pagination"""
    page = request.args.get('page', 1, type=int)
    per_page = JOURNALS_PER_PAGE

    # Get all portfolio decision journals with pagination
    pagination = DecisionJournal.query.filter_by(
        user_id=current_user.id,
        is_portfolio_decision=True
    ).order_by(DecisionJournal.decision_date.desc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    journals = pagination.items

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

    return render_template('decision_journal_list.html',
                          journals=journals,
                          pagination=pagination,
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

    return render_template('decision_journal_detail.html',
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

    return render_template('sell_postmortem.html',
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
            'date': thesis.created_at.date() if thesis.created_at else now_utc().date(),
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

    return render_template('investment_journey.html',
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

            # Get bull case points (using constants for field limit)
            bull_case = [
                request.form.get(f'bull_case_{i}', '').strip()
                for i in range(1, MAX_DYNAMIC_FORM_FIELDS + 1)
                if request.form.get(f'bull_case_{i}', '').strip()
            ]

            # Get bear case points
            bear_case = [
                request.form.get(f'bear_case_{i}', '').strip()
                for i in range(1, MAX_DYNAMIC_FORM_FIELDS + 1)
                if request.form.get(f'bear_case_{i}', '').strip()
            ]

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

    return render_template('add_thesis_version.html',
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
    # Get all active positions with eager loading
    positions = PortfolioPosition.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).options(
        joinedload(PortfolioPosition.company).joinedload(Company.sector)
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

    # Calculate annualized return (CAGR)
    earliest_date = db.session.query(func.min(PortfolioPosition.first_purchase_date)).filter_by(
        user_id=current_user.id,
        is_active=True
    ).scalar()

    annualized_return = Decimal('0.00')
    years_held = 0
    if earliest_date and portfolio_value['total_cost'] > 0:
        days_held = (now_utc().date() - earliest_date).days
        if days_held > 0:
            years_held = days_held / 365.25
            if total_return_pct:
                annualized_return = calculate_cagr(float(total_return_pct), days_held)

    # Calculate win rate using utility
    win_rate = calculate_win_rate(positions)
    winning_positions = count_positions_by_status(positions)['winning']
    total_positions = len(positions)

    # Calculate average holding period using utility
    avg_hold_days = calculate_average_holding_period(positions)

    # Get top and bottom performers using utilities
    top_performers = get_top_performers(positions, limit=DEFAULT_TOP_PERFORMERS_LIMIT)
    bottom_performers = get_bottom_performers(positions, limit=DEFAULT_BOTTOM_PERFORMERS_LIMIT)

    # Calculate monthly performance (last 12 months)
    monthly_performance = []
    for i in range(11, -1, -1):
        month_date = now_utc().date() - timedelta(days=i*30)
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

    return render_template('portfolio_basic_analytics.html',
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

    # Calculate holding period performance using utility
    hold_period_stats = calculate_holding_period_stats(active_positions)

    # Decision Quality Matrix
    # Good Process = Research-backed, Bad Process = No research
    good_process_good_outcome = sum(1 for p in research_positions if p.unrealized_gain_loss and p.unrealized_gain_loss > 0)
    good_process_bad_outcome = sum(1 for p in research_positions if p.unrealized_gain_loss and p.unrealized_gain_loss <= 0)
    bad_process_good_outcome = sum(1 for p in non_research_positions if p.unrealized_gain_loss and p.unrealized_gain_loss > 0)
    bad_process_bad_outcome = sum(1 for p in non_research_positions if p.unrealized_gain_loss and p.unrealized_gain_loss <= 0)

    # Recent decisions
    recent_decisions = Transaction.query.filter_by(
        user_id=current_user.id
    ).filter(
        Transaction.type.in_(['BUY', 'SELL'])
    ).order_by(Transaction.date.desc()).limit(RECENT_DECISIONS_LIMIT).all()

    # Confidence Calibration Analysis
    # Get all BUY journals with confidence scores and actual returns
    journals_with_confidence = []
    for journal in all_journals:
        if journal.confidence_score and journal.decision_type == 'BUY':
            position = next((p for p in all_positions if p.company_id == journal.company_id), None)
            if position and position.unrealized_gain_loss_pct:
                journals_with_confidence.append({
                    'confidence': journal.confidence_score,
                    'return': float(position.unrealized_gain_loss_pct)
                })

    # Calculate confidence calibration stats using utility
    confidence_stats = calculate_confidence_stats(journals_with_confidence)

    # Performance vs Expectations Analysis
    # Get all journals with expected returns and compare to actual
    expectations_analysis = []
    for journal in all_journals:
        if journal.expected_return and journal.decision_type == 'BUY':
            position = next((p for p in all_positions if p.company_id == journal.company_id), None)
            if position and position.unrealized_gain_loss_pct:
                expected = journal.expected_return
                actual = float(position.unrealized_gain_loss_pct)
                diff = actual - expected
                met_expectation = actual >= expected

                expectations_analysis.append({
                    'company': position.company,
                    'expected': expected,
                    'actual': actual,
                    'diff': diff,
                    'met': met_expectation
                })

    # Calculate summary stats
    expectations_met_count = sum(1 for item in expectations_analysis if item['met'])
    expectations_total_count = len(expectations_analysis)
    expectations_met_pct = (expectations_met_count / expectations_total_count * 100) if expectations_total_count > 0 else 0

    return render_template('decisions_intelligence.html',
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
                          recent_decisions=recent_decisions,
                          confidence_stats=confidence_stats,
                          expectations_analysis=expectations_analysis,
                          expectations_met_count=expectations_met_count,
                          expectations_total_count=expectations_total_count,
                          expectations_met_pct=expectations_met_pct)

@portfolio_bp.route('/analytics/research-correlation')
@login_required
def research_correlation():
    """Research Quality → Returns Correlation Dashboard"""
    from app.services.portfolio_intelligence import (
        get_correlation_data,
        get_learning_insights
    )
    
    correlation_data = get_correlation_data(current_user.id)
    
    insights = []
    if correlation_data.has_sufficient_data:
        insights = get_learning_insights(current_user.id)
    
    return render_template('research_correlation.html',
                          correlation_data=correlation_data,
                          insights=insights)
    

@portfolio_bp.route('/checkpoints')
@login_required
def checkpoint_reminders():
    """Checkpoint Reminders Dashboard"""    
    checkpoints = get_upcoming_checkpoints(current_user.id, days_ahead=DEFAULT_CHECKPOINT_LOOKBACK_DAYS)
    
    return render_template('checkpoint_reminders.html',
                          checkpoints=checkpoints)
    
@portfolio_bp.route('/thesis-reality')
@login_required
def thesis_reality():
    """Thesis vs Reality Dashboard"""    
    positions = get_thesis_reality_check(current_user.id)
    
    # Count by status
    status_counts = {
        'exceeding': 0,
        'on_track': 0,
        'behind': 0,
        'needs_attention': 0
    }
    
    for pos in positions:
        if pos.status in status_counts:
            status_counts[pos.status] += 1
    
    return render_template('thesis_reality.html',
                          positions=positions,
                          status_counts=status_counts)    

@portfolio_bp.route('/learning-insights')
@login_required
def learning_insights():
    """
    Learning Insights Dashboard
    Shows personalized patterns from trading history
    """
    # Get outcomes for stats
    outcomes = ResearchOutcome.query.filter(
        ResearchOutcome.user_id == current_user.id,
        ResearchOutcome.realized_return_pct.isnot(None)
    ).all()
    
    current_trades = len(outcomes)
    has_sufficient_data = current_trades >= MIN_TRADES_FOR_INSIGHTS
    
    # Initialize default values
    insights_by_category = {
        'edge': [],
        'winning_pattern': [],
        'warning': [],
        'improvement': []
    }
    stats = {
        'total_trades': 0,
        'win_rate': 0,
        'avg_return': 0,
        'avg_hold_days': 0
    }
    has_quality_edge = False
    has_holding_insight = False
    has_sector_insight = False
    
    if has_sufficient_data:
        # Get insights
        insights = get_learning_insights(current_user.id)
        
        # Group insights by category
        for insight in insights:
            category = insight.category
            if category in insights_by_category:
                insights_by_category[category].append(insight)
            else:
                insights_by_category['improvement'].append(insight)
        
        # Calculate stats
        returns = [float(o.realized_return_pct) for o in outcomes]
        wins = [r for r in returns if r > 0]
        
        hold_days = []
        for o in outcomes:
            if o.exit_date and o.entry_date:
                hold_days.append((o.exit_date - o.entry_date).days)
        
        stats = {
            'total_trades': len(outcomes),
            'win_rate': (len(wins) / len(returns) * 100) if returns else 0,
            'avg_return': sum(returns) / len(returns) if returns else 0,
            'avg_hold_days': sum(hold_days) // len(hold_days) if hold_days else 0
        }
        
        # Check for specific insight types to show relevant actions
        for insight in insights:
            if 'research' in insight.title.lower() or 'quality' in insight.title.lower():
                has_quality_edge = True
            if 'hold' in insight.title.lower() or 'patience' in insight.title.lower():
                has_holding_insight = True
            if 'sector' in insight.title.lower():
                has_sector_insight = True
    
    return render_template('learning_insights.html',
                          has_sufficient_data=has_sufficient_data,
                          min_trades_needed=MIN_TRADES_FOR_INSIGHTS,
                          current_trades=current_trades,
                          insights_by_category=insights_by_category,
                          stats=stats,
                          has_quality_edge=has_quality_edge,
                          has_holding_insight=has_holding_insight,
                          has_sector_insight=has_sector_insight)
    

@portfolio_bp.route('/intelligence')
@login_required
def intelligence_hub():
    """
    Investment Intelligence Hub
    Central dashboard linking all intelligence features with summary metrics
    """

    # Initialize service
    intel_service = PortfolioIntelligenceService(current_user.id)
    
    # ========================================
    # HEALTH BAR - Quick overview metrics
    # ========================================
    
    # Get portfolio positions with eager loading
    positions = PortfolioPosition.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).options(
        joinedload(PortfolioPosition.company).joinedload(Company.sector)
    ).all()
    
    # Calculate total return
    total_value = sum(float(p.current_value or 0) for p in positions)
    total_cost = sum(float(p.total_cost or 0) for p in positions)
    total_return = ((total_value - total_cost) / total_cost * 100) if total_cost > 0 else 0
    
    # Win rate from outcomes
    outcomes = ResearchOutcome.query.filter(
        ResearchOutcome.user_id == current_user.id,
        ResearchOutcome.realized_return_pct.isnot(None)
    ).all()
    
    wins = [o for o in outcomes if float(o.realized_return_pct) > 0]
    win_rate = (len(wins) / len(outcomes) * 100) if outcomes else 0
    
    # Checkpoints
    checkpoint_summary = intel_service.get_checkpoint_summary()
    
    # Thesis reality
    thesis_positions = intel_service.get_thesis_reality_check()
    needs_attention = len([p for p in thesis_positions if p.status == 'needs_attention'])
    
    # Average quality grade
    if outcomes:
        avg_score = sum(o.research_quality_score or 0 for o in outcomes) / len(outcomes)
        if avg_score >= GRADE_A_THRESHOLD:
            avg_grade = 'A'
        elif avg_score >= GRADE_B_THRESHOLD:
            avg_grade = 'B'
        elif avg_score >= GRADE_C_THRESHOLD:
            avg_grade = 'C'
        elif avg_score >= GRADE_D_THRESHOLD:
            avg_grade = 'D'
        else:
            avg_grade = 'F'
    else:
        avg_grade = '—'
    
    health = {
        'total_return': total_return,
        'win_rate': win_rate,
        'overdue_checkpoints': checkpoint_summary.get('overdue_count', 0),
        'needs_attention': needs_attention,
        'avg_quality_grade': avg_grade
    }
    
    # ========================================
    # ALERTS - Action items
    # ========================================
    alerts = []
    
    # Overdue checkpoints
    checkpoints_data = intel_service.get_upcoming_checkpoints(days_ahead=DEFAULT_CHECKPOINT_LOOKBACK_DAYS)
    for cp in checkpoints_data.get('overdue', [])[:3]:
        alerts.append({
            'type': 'danger',
            'icon': 'exclamation-triangle-fill',
            'message': f'{cp.company_ticker}: {cp.metric} is overdue',
            'action': 'Review',
            'link': url_for('portfolio.checkpoint_reminders')
        })
    
    # Positions needing attention
    for pos in thesis_positions:
        if pos.status == 'needs_attention':
            alerts.append({
                'type': 'warning',
                'icon': 'exclamation-circle',
                'message': f'{pos.company_ticker} thesis diverging ({pos.actual_return_pct:+.1f}%)',
                'action': 'Check',
                'link': url_for('portfolio.thesis_reality')
            })
    
    # This week checkpoints
    for cp in checkpoints_data.get('this_week', [])[:2]:
        alerts.append({
            'type': 'info',
            'icon': 'calendar-event',
            'message': f'{cp.company_ticker}: {cp.metric} due this week',
            'action': 'View',
            'link': url_for('portfolio.checkpoint_reminders')
        })
    
    # Learning insight (if new patterns detected)
    insights = get_learning_insights(current_user.id) if len(outcomes) >= MIN_TRADES_FOR_INSIGHTS else []
    high_importance = [i for i in insights if i.importance == 'high']
    if high_importance:
        alerts.append({
            'type': 'success',
            'icon': 'lightbulb-fill',
            'message': f'New insight: "{high_importance[0].title}"',
            'action': 'View',
            'link': url_for('portfolio.learning_insights')
        })
    
    
    portfolio_warnings = get_portfolio_warnings(current_user.id)
    for warning in portfolio_warnings:
        if warning.severity in ['high', 'medium']:
            alerts.append({
                'type': 'danger' if warning.severity == 'high' else 'warning',
                'icon': 'shield-exclamation',
                'message': f'{warning.title}: {warning.message[:50]}...',
                'action': 'Review',
                'link': url_for('portfolio.dashboard')
            })
    # ========================================
    # CARD DATA - Individual sections
    # ========================================
    
    # Performance Card
    winning_positions = len([p for p in positions if (p.unrealized_gain_loss or 0) > 0])
    losing_positions = len([p for p in positions if (p.unrealized_gain_loss or 0) < 0])
    
    top_performer = None
    if positions:
        best = max(positions, key=lambda p: float(p.unrealized_gain_loss_pct or 0))
        if best.company:
            top_performer = {
                'ticker': best.company.ticker_symbol,
                'return': float(best.unrealized_gain_loss_pct or 0)
            }
    
    performance = {
        'has_data': len(positions) > 0,
        'total_return': total_return,
        'positions_count': len(positions),
        'winning': winning_positions,
        'losing': losing_positions,
        'top_performer': top_performer
    }
    
    # Decisions Card
    research_journals = DecisionJournal.query.filter(
        DecisionJournal.user_id == current_user.id,
        DecisionJournal.is_portfolio_decision == True,
        DecisionJournal.decision_type == 'BUY',
        DecisionJournal.linked_research_id.isnot(None)
    ).all()
    
    no_research_journals = DecisionJournal.query.filter(
        DecisionJournal.user_id == current_user.id,
        DecisionJournal.is_portfolio_decision == True,
        DecisionJournal.decision_type == 'BUY',
        DecisionJournal.non_research_source.isnot(None)
    ).all()
    
    # Calculate returns for each category
    def get_avg_return(journals):
        returns = []
        for j in journals:
            pos = next((p for p in positions if p.company_id == j.company_id), None)
            if pos and pos.unrealized_gain_loss_pct is not None:
                returns.append(float(pos.unrealized_gain_loss_pct))
        return sum(returns) / len(returns) if returns else 0
    
    research_return = get_avg_return(research_journals)
    no_research_return = get_avg_return(no_research_journals)
    
    decisions = {
        'has_data': len(research_journals) > 0 or len(no_research_journals) > 0,
        'research_return': research_return,
        'no_research_return': no_research_return,
        'research_advantage': research_return - no_research_return
    }
    
    # Correlation Card
    correlation_data = get_correlation_data(current_user.id)
    
    correlation = {
        'has_data': correlation_data.has_sufficient_data,
        'research_advantage': correlation_data.research_advantage,
        'total_outcomes': correlation_data.total_outcomes,
        'best_grade': correlation_data.best_grade,
        'min_needed': MIN_TRADES_FOR_INSIGHTS
    }
    
    # Checkpoints Card
    checkpoints = {
        'overdue': checkpoint_summary.get('overdue_count', 0),
        'this_week': checkpoint_summary.get('this_week_count', 0),
        'upcoming': checkpoint_summary.get('upcoming_count', 0),
        'total': checkpoint_summary.get('total_active', 0)
    }
    
    # Thesis Card
    thesis = {
        'has_positions': len(thesis_positions) > 0,
        'exceeding': len([p for p in thesis_positions if p.status == 'exceeding']),
        'on_track': len([p for p in thesis_positions if p.status == 'on_track']),
        'behind': len([p for p in thesis_positions if p.status == 'behind']),
        'needs_attention': needs_attention
    }
    
    # Learning Card
    insights_by_cat = {'edge': [], 'winning_pattern': [], 'warning': [], 'improvement': []}
    for insight in insights:
        if insight.category in insights_by_cat:
            insights_by_cat[insight.category].append(insight)
    
    learning = {
        'has_insights': len(insights) > 0,
        'edge_count': len(insights_by_cat['edge']),
        'patterns_count': len(insights_by_cat['winning_pattern']),
        'warnings_count': len(insights_by_cat['warning']),
        'total_trades': len(outcomes),
        'top_insight': insights[0].title if insights else None,
        'min_needed': MIN_TRADES_FOR_INSIGHTS
    }
    
    return render_template('intelligence_hub.html',
                          health=health,
                          alerts=alerts,
                          performance=performance,
                          decisions=decisions,
                          correlation=correlation,
                          checkpoints=checkpoints,
                          thesis=thesis,
                          learning=learning)
    
# ============================================================
# ADD THIS ROUTE TO app/portfolio/routes.py
# Place after add_transaction route
# ============================================================

@portfolio_bp.route('/api/check-warnings', methods=['POST'])
@login_required
def check_transaction_warnings():
    """
    API endpoint to check warnings before transaction.
    Called via AJAX as user fills out the form.
    
    Request JSON:
        {
            "company_id": 123,
            "transaction_type": "BUY",
            "quantity": 100,
            "price_per_share": 150.00
        }
    
    Response JSON:
        {
            "warnings": [...],
            "count": 3,
            "has_high_severity": true
        }
    """    
    data = request.get_json()
    
    if not data:
        return jsonify({'warnings': [], 'count': 0, 'has_high_severity': False})
    
    company_id = data.get('company_id')
    transaction_type = data.get('transaction_type')
    quantity = data.get('quantity')
    price_per_share = data.get('price_per_share')
    
    warnings = []
    
    # Only check warnings for BUY transactions
    if transaction_type == 'BUY' and company_id and quantity and price_per_share:
        try:
            amount = float(quantity) * float(price_per_share)
            engine = IntelligenceEngine(current_user.id)
            warnings = engine.check_buy_transaction(int(company_id), amount)
        except (ValueError, TypeError) as e:
            # Invalid input, return no warnings
            pass
    
    # Convert warnings to JSON-serializable format
    warnings_data = [
        {
            'code': w.code,
            'severity': w.severity,
            'category': w.category,
            'title': w.title,
            'message': w.message,
            'data': w.data,
            'action_url': w.action_url,
            'dismissible': w.dismissible
        }
        for w in warnings
    ]
    
    has_high = any(w['severity'] == 'high' for w in warnings_data)
    
    return jsonify({
        'warnings': warnings_data,
        'count': len(warnings_data),
        'has_high_severity': has_high
    })
    
@portfolio_bp.route('/api/check-sell-warnings', methods=['POST'])
@login_required
def check_sell_transaction_warnings():
    """API endpoint to check warnings before SELL transaction."""
    
    data = request.get_json()
    company_id = data.get('company_id')
    shares = data.get('shares')
    
    warnings = check_sell_warnings(current_user.id, company_id, shares) if company_id and shares else []
    
    return jsonify({
        'warnings': [w.__dict__ for w in warnings],
        'count': len(warnings)
    })