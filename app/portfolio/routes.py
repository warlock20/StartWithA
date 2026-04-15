# app/portfolio/routes.py

import logging
from datetime import datetime
from decimal import Decimal
from flask import render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from app import db

# Configure logger
logger = logging.getLogger(__name__)
from app.models import (
    Transaction, PortfolioPosition, Company, DecisionJournal,
    ResearchProject, DestinationCheckpoint, ThesisEvolution, ResearchOutcome,
    BackgroundTask, PortfolioUIInsight, JournalEntry
)
from app.services.currency_service import CurrencyService
from app.services.price_service import PriceService
from app.services.too_hard_service import TooHardBasketService
from app.utils.time_utils import now_utc, ensure_timezone_aware
from app.utils.response_utils import json_error, json_unauthorized
from app.utils.portfolio_utils import (
     filter_positions_by_performance,
    calculate_holding_period_stats,
    calculate_confidence_stats, count_positions_by_status
)
from app.services.background_tasks import BackgroundTaskService

from app.constants import (
    MIN_TRADES_FOR_INSIGHTS,
    RECENT_TRANSACTIONS_LIMIT, RECENT_DECISIONS_LIMIT, UPCOMING_CHECKPOINTS_LIMIT,
    DEFAULT_CHECKPOINT_LOOKBACK_DAYS,
    MAX_DYNAMIC_FORM_FIELDS,
    GRADE_A_THRESHOLD, GRADE_B_THRESHOLD, GRADE_C_THRESHOLD, GRADE_D_THRESHOLD
)
from app.services.portfolio_intelligence import (
    get_thesis_reality_check, PortfolioIntelligenceService,
    get_learning_insights, get_correlation_data
    )
from app.services.intelligence_engine import get_portfolio_warnings
from app.services.portfolio_ai_analytics import PortfolioAIAnalytics
from app.services.portfolio_data_extractor import PortfolioDataExtractor
from app.services.cash_service import CashService

import json
# Import blueprint from current package (avoids circular import)
from . import portfolio_bp

#############################
#### Dashboard  ####
#############################

@portfolio_bp.route('/')
@login_required
def dashboard():
    """Portfolio dashboard — renders instantly with cached data.

    Prices are refreshed asynchronously via AJAX after the page loads
    (see refresh-position endpoint in api_routes.py).
    """
    # Get all active positions with eager loading
    positions = PortfolioPosition.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).options(
        joinedload(PortfolioPosition.company)
    ).all()

    # Calculate portfolio totals from cached DB data (no API calls)
    total_value = Decimal('0.00')
    total_cost = Decimal('0.00')
    total_unrealized = Decimal('0.00')

    for pos in positions:
        if pos.current_value:
            total_value += pos.current_value
        total_cost += pos.total_cost
        if pos.unrealized_gain_loss:
            total_unrealized += pos.unrealized_gain_loss

    total_pct = (total_unrealized / total_cost * 100) if total_cost > 0 else Decimal('0.00')
    cash_balance = Decimal(str(current_user.cash_balance)) if current_user.cash_balance else Decimal('0.00')

    portfolio_value = {
        'total_value': total_value + cash_balance,
        'total_cost': total_cost,
        'total_unrealized_gain_loss': total_unrealized,
        'total_unrealized_gain_loss_pct': total_pct,
        'positions_count': len(positions),
        'cash_balance': cash_balance,
        'invested_value': total_value,
    }

    # Identify stale positions for async refresh
    stale_company_ids = [
        pos.company_id for pos in positions
        if PriceService.should_update_price(pos)
    ]

    # Calculate gains and losses counts using utility
    status_counts = count_positions_by_status(positions)
    gains_count = status_counts['winning']
    losses_count = status_counts['losing']

    # Get user currency settings
    user_currency = current_user.base_currency
    currency_symbol = CurrencyService.get_currency_symbol(user_currency)

    # Serialize positions for Tabulator
    holdings_json = json.dumps([{
        'ticker': pos.company.ticker_symbol,
        'name': pos.company.name,
        'shares': float(pos.total_shares) if pos.total_shares else 0,
        'avg_cost': float(round(pos.average_cost_basis, 2)) if pos.average_cost_basis else None,
        'current_price': float(round(pos.current_price, 2)) if pos.current_price else None,
        'current_value': float(round(pos.current_value)) if pos.current_value else None,
        'gain_loss': float(round(pos.unrealized_gain_loss)) if pos.unrealized_gain_loss else None,
        'gain_loss_pct': float(round(pos.unrealized_gain_loss_pct, 1)) if pos.unrealized_gain_loss_pct else None,
        'days_held': pos.days_held or 0,
        'company_id': pos.company_id,
        'position_url': url_for('portfolio.position_detail', company_id=pos.company_id),
        'add_tx_url': url_for('portfolio.add_transaction', company_id=pos.company_id),
    } for pos in positions])

    # Cash setup: infer initial deposit for existing users who haven't set up cash tracking
    inferred_deposit = None
    if not current_user.cash_setup_complete and portfolio_value['positions_count'] > 0:
        inferred_deposit = float(CashService.infer_initial_deposit(current_user.id))

    return render_template('portfolio_dashboard.html',
                          positions=positions,
                          holdings_json=holdings_json,
                          portfolio_value=portfolio_value,
                          gains_count=gains_count,
                          losses_count=losses_count,
                          stale_company_ids=json.dumps(stale_company_ids),
                          updated_time='just now',
                          currency_symbol=currency_symbol,
                          inferred_deposit=inferred_deposit)


@portfolio_bp.route('/cash/setup', methods=['POST'])
@login_required
def cash_setup():
    """One-time initial capital confirmation for cash tracking."""
    amount = Decimal(request.form.get('initial_capital', '0'))
    if amount > 0:
        CashService.create_initial_deposit(current_user.id, amount, current_user.base_currency)
    current_user.cash_setup_complete = True
    db.session.commit()
    flash('Initial capital recorded. Cash tracking is now active!', 'success')
    return redirect(url_for('portfolio.dashboard'))

############################
#### Postion Related ########
#############################

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

    # Price is refreshed async via AJAX after page loads
    price_stale = PriceService.should_update_price(position)

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

    # Stock's native trading currency (for dual-currency display)
    stock_currency = position.currency or company.reporting_currency or user_currency
    stock_currency_symbol = CurrencyService.get_currency_symbol(stock_currency)

    return render_template('position_detail.html',
                          company=company,
                          position=position,
                          transactions=transactions,
                          decision_journal=decision_journal,
                          checkpoints=checkpoints,
                          research_project=research_project,
                          price_stale=price_stale,
                          user_currency=user_currency,
                          currency_symbol=currency_symbol,
                          stock_currency=stock_currency,
                          stock_currency_symbol=stock_currency_symbol,
                          today=now_utc().date())


@portfolio_bp.route('/position/<int:company_id>/journey')
@login_required
def investment_journey(company_id):
    """Redirect to unified Company Journey page."""
    return redirect(url_for('companies.company_journey', company_id=company_id))


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
            return redirect(url_for('companies.company_journey', company_id=company_id))

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

    currency_symbol = CurrencyService.get_currency_symbol(company.reporting_currency or 'USD')

    return render_template('add_thesis_version.html',
                          company=company,
                          position=position,
                          current_thesis=current_thesis,
                          next_version=next_version,
                          currency_symbol=currency_symbol)


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



###########################
#### Analytics Related ####
###########################


def _get_cached_chart_data(user_id, time_periods):
    """Get chart data from cache or start a background task to compute it.

    Returns:
        (chart_data, chart_task_id) — chart_data is None if no cache yet,
        chart_task_id is set when a background task is running/just started.
    """
    from app.services.config_service import get_config, ConfigKeys
    from datetime import timedelta

    task_type = f'chart_data:{time_periods}'

    # 1. Check for a running task — don't start another
    running = BackgroundTask.query.filter_by(
        user_id=user_id,
        task_type=task_type,
        status='running'
    ).first()

    if running:
        return None, running.id

    # 2. Check for completed task within TTL
    ttl_hours = get_config(ConfigKeys.CHART_DATA_CACHE_TTL_HOURS, default=24)
    try:
        ttl_hours = float(ttl_hours)
    except (TypeError, ValueError):
        ttl_hours = 24

    latest = BackgroundTask.query.filter_by(
        user_id=user_id,
        task_type=task_type,
        status='completed'
    ).order_by(BackgroundTask.completed_at.desc()).first()

    if latest and latest.result and latest.completed_at:
        age = now_utc() - ensure_timezone_aware(latest.completed_at)
        if age < timedelta(hours=ttl_hours):
            # Fresh cache — serve it
            result = json.loads(latest.result)
            return result.get('chart_data'), None
        else:
            # Stale — serve stale data but kick off a refresh
            stale_data = json.loads(latest.result).get('chart_data')
            task_id = BackgroundTaskService.start_chart_data_task(user_id, time_periods)
            return stale_data, task_id

    # 3. No cache at all — start background task
    task_id = BackgroundTaskService.start_chart_data_task(user_id, time_periods)
    return None, task_id


def _get_cached_module_analysis(user_id, template_name):
    """Load cached results for a modular analysis (sector momentum, tax optimization, etc.).

    Returns the analysis dict if a completed task exists, otherwise None.
    """
    task = BackgroundTask.query.filter_by(
        user_id=user_id,
        task_type=f'portfolio_analysis:{template_name}',
        status='completed'
    ).order_by(BackgroundTask.completed_at.desc()).first()

    if task and task.result:
        result = json.loads(task.result)
        return result.get('analysis')
    return None


# Allowed templates for the AJAX run endpoint
ALLOWED_ANALYSIS_TEMPLATES = {
    'sector_momentum_analysis',
    'tax_optimization_analysis',
}


@portfolio_bp.route('/analytics')
@login_required
def analytics():
    """
    AI-Powered Portfolio Analytics (Async with Celery)

    Flow:
    1. Check cache - if exists, show results
    2. Check running task - if exists, show loading page
    3. If refresh=true, start new task and show loading page
    4. Otherwise, show placeholder with "Run Analysis" button
    """
    force_refresh = request.args.get('refresh', 'false').lower() == 'true'
    template_name = 'portfolio_raw_trade_analysis'  # Using deep behavioral analysis

    # Chart data — served from cache, computed in background
    time_period = request.args.get('period', '12')
    try:
        time_periods = int(time_period)
        if time_periods not in [1, 3, 6, 12, 24, 36]:
            time_periods = 12
    except (ValueError, TypeError):
        time_periods = 12

    chart_data, chart_task_id = _get_cached_chart_data(current_user.id, time_periods)

    # Load cached modular analyses (sector momentum, tax optimization, etc.)
    sector_momentum = _get_cached_module_analysis(current_user.id, 'sector_momentum_analysis')
    tax_optimization = _get_cached_module_analysis(current_user.id, 'tax_optimization_analysis')

    # 1. HIGHEST PRIORITY: Check if there's a running task
    # Always show loading page if task is running, even if old cache exists
    running_task = BackgroundTask.query.filter_by(
        user_id=current_user.id,
        task_type=f'portfolio_analysis:{template_name}',
        status='running'
    ).first()

    if running_task:
        # Task is running, show loading page
        return render_template('portfolio_analytics_loading.html',
                              task_id=running_task.id,
                              chart_data=chart_data,
                              chart_task_id=chart_task_id,
                              selected_period=time_periods)

    # 2. Check for latest completed task in database (cache)
    if not force_refresh:
        latest_task = BackgroundTask.query.filter_by(
            user_id=current_user.id,
            task_type=f'portfolio_analysis:{template_name}',
            status='completed'
        ).order_by(BackgroundTask.completed_at.desc()).first()

        if latest_task and latest_task.result:
            # We have a completed analysis, show it
            result = json.loads(latest_task.result)
            logger.info(result)
            insights = result.get('analysis')
            if insights:
                has_error = insights.get('metadata', {}).get('error') is not None
                return render_template('portfolio_basic_analytics.html',
                                      insights=insights,
                                      has_error=has_error,
                                      chart_data=chart_data,
                                      selected_period=time_periods,
                                      sector_momentum=sector_momentum,
                                      tax_optimization=tax_optimization)

    # 3. If force_refresh=true, check tokens then start background task
    if force_refresh:
        # Check tokens BEFORE starting expensive AI task (estimate: 10,000 tokens for portfolio analysis)
        if not current_user.can_use_ai_tokens(10000):
            # User has hit token limit - show cached analysis with error message
            logger.warning(f"User {current_user.id} attempted portfolio analysis but hit token limit ({current_user.ai_tokens_used}/{current_user.ai_tokens_limit})")

            # Try to show cached analysis if available
            latest_task = BackgroundTask.query.filter_by(
                user_id=current_user.id,
                task_type=f'portfolio_analysis:{template_name}',
                status='completed'
            ).order_by(BackgroundTask.completed_at.desc()).first()

            if latest_task and latest_task.result:
                # Show cached analysis with token limit error
                result = json.loads(latest_task.result)
                insights = result.get('analysis')
                flash(f"AI Token Limit Reached: You've used {current_user.ai_tokens_used:,} of {current_user.ai_tokens_limit:,} tokens. Showing previous analysis. Your limit resets on {current_user.ai_tokens_reset_date.strftime('%b %d, %Y') if current_user.ai_tokens_reset_date else 'unknown date'}.", 'warning')
                return render_template('portfolio_basic_analytics.html',
                                      insights=insights,
                                      has_error=False,
                                      chart_data=chart_data,
                                      selected_period=time_periods,
                                      sector_momentum=sector_momentum,
                                      tax_optimization=tax_optimization,
                                      show_run_button=False)  # Don't show run button - they're at limit
            else:
                # No cache and no tokens - show placeholder with error
                analytics_service = PortfolioAIAnalytics(user_id=current_user.id)
                placeholder_insights = analytics_service._get_placeholder_response(template_name)
                flash(f"AI Token Limit Reached: You've used {current_user.ai_tokens_used:,} of {current_user.ai_tokens_limit:,} tokens. Cannot generate new analysis. Your limit resets on {current_user.ai_tokens_reset_date.strftime('%b %d, %Y') if current_user.ai_tokens_reset_date else 'unknown date'}.", 'error')
                return render_template('portfolio_basic_analytics.html',
                                      insights=placeholder_insights,
                                      has_error=True,
                                      chart_data=chart_data,
                                      selected_period=time_periods,
                                      sector_momentum=sector_momentum,
                                      tax_optimization=tax_optimization,
                                      show_run_button=False)

        # User has enough tokens - start task
        task_id = BackgroundTaskService.start_portfolio_analysis(current_user.id, template_name)
        session[f'portfolio_analysis_task_{current_user.id}'] = task_id
        return render_template('portfolio_analytics_loading.html',
                              task_id=task_id,
                              chart_data=chart_data,
                              chart_task_id=chart_task_id,
                              selected_period=time_periods)

    # 4. No completed analysis, no running task, no refresh requested - show placeholder
    analytics_service = PortfolioAIAnalytics(user_id=current_user.id)
    placeholder_insights = analytics_service._get_placeholder_response(template_name)
    return render_template('portfolio_basic_analytics.html',
                          insights=placeholder_insights,
                          has_error=False,
                          chart_data=chart_data,
                          selected_period=time_periods,
                          sector_momentum=sector_momentum,
                          tax_optimization=tax_optimization,
                          show_run_button=True)


@portfolio_bp.route('/analytics/status/<task_id>')
@login_required
def analytics_status(task_id):
    """
    Check the status of a running portfolio analytics task.
    Returns JSON for AJAX polling from loading page.
    """
    # Get task status from database
    task_status = BackgroundTaskService.get_task_status(task_id)

    if not task_status:
        return jsonify({
            'state': 'NOT_FOUND',
            'current': 0,
            'total': 100,
            'status': 'Task not found',
            'error': 'Task ID not found in database'
        })

    # Map database status to response format
    response = {
        'current': 0,
        'total': 100,
        'status': ''
    }

    if task_status['status'] == 'pending':
        response['state'] = 'PENDING'
        response['status'] = 'Task is waiting to start...'
        response['current'] = 10
    elif task_status['status'] == 'running':
        response['state'] = 'STARTED'
        response['status'] = 'Analysis in progress...'
        response['current'] = 50
    elif task_status['status'] == 'completed':
        response['state'] = 'SUCCESS'
        response['status'] = 'Analysis completed!'
        response['current'] = 100
        # Include the result
        if task_status.get('result'):
            response['result'] = task_status['result']
    elif task_status['status'] == 'failed':
        response['state'] = 'FAILURE'
        response['status'] = 'Analysis failed'
        response['current'] = 100
        response['error'] = task_status.get('error', 'Unknown error')
    else:
        response['state'] = 'UNKNOWN'
        response['status'] = f"Task state: {task_status['status']}"

    return jsonify(response)


@portfolio_bp.route('/analytics/run/<template_name>', methods=['POST'])
@login_required
def analytics_run_module(template_name):
    """
    Start a modular analysis via AJAX.
    Returns JSON with task_id for polling via analytics_status.
    """
    if template_name not in ALLOWED_ANALYSIS_TEMPLATES:
        return json_error(f'Unknown analysis type: {template_name}')

    # Check for already-running task
    running = BackgroundTask.query.filter_by(
        user_id=current_user.id,
        task_type=f'portfolio_analysis:{template_name}',
        status='running'
    ).first()
    if running:
        return jsonify({'task_id': running.id, 'status': 'already_running'})

    # Check token budget
    if not current_user.can_use_ai_tokens(5000):
        return json_error('AI token limit reached', status_code=429)

    # Start background task
    task_id = BackgroundTaskService.start_portfolio_analysis(
        current_user.id, template_name
    )
    return jsonify({'task_id': task_id, 'status': 'started'})


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


#############################
#### Analytics History API  ####
#############################

@portfolio_bp.route('/api/analytics/history')
@login_required
def analytics_history():
    """
    Get historical portfolio analyses for trend tracking.

    Query params:
        template: Filter by template name (optional)
        limit: Max records to return (default 10, max 50)

    Returns:
        JSON list of historical analyses (summaries only, not full insights)
    """
    template_name = request.args.get('template', None)

    limit_raw = request.args.get('limit')
    if limit_raw is None:
        limit = 10
    else:
        try:
            limit = int(limit_raw)
        except (ValueError, TypeError):
            return jsonify({
                'success': False,
                'error': "Invalid 'limit' parameter; it must be an integer."
            }), 400
    limit = min(limit, 50)

    history = PortfolioUIInsight.get_history(
        user_id=current_user.id,
        template_name=template_name,
        limit=limit
    )

    return jsonify({
        'success': True,
        'count': len(history),
        'analyses': [h.to_summary_dict() for h in history]
    })


@portfolio_bp.route('/api/analytics/history/<int:insight_id>')
@login_required
def get_historical_analysis(insight_id):
    """
    Get a specific historical analysis with full insights.

    Args:
        insight_id: The PortfolioUIInsight ID

    Returns:
        JSON with full analysis data
    """
    insight = PortfolioUIInsight.query.get(insight_id)

    if not insight:
        return json_error('Analysis not found', status_code=404)

    if insight.user_id != current_user.id:
        return json_unauthorized('Unauthorized')

    return jsonify({
        'success': True,
        'analysis': insight.to_dict()
    })


@portfolio_bp.route('/api/analytics/trends')
@login_required
def analytics_trends():
    """
    Get trend data from historical analyses for visualization.

    Extracts key metrics over time for trend charts.

    Query params:
        template: Filter by template name (optional)
        limit: Max records to analyze (default 10)

    Returns:
        JSON with trend data points
    """
    template_name = request.args.get('template', 'portfolio_raw_trade_analysis')

    limit_raw = request.args.get('limit')
    if limit_raw is None:
        limit = 10
    else:
        try:
            limit = int(limit_raw)
        except (ValueError, TypeError):
            return jsonify({
                'success': False,
                'error': "Invalid 'limit' parameter; it must be an integer."
            }), 400
    limit = min(limit, 50)

    history = PortfolioUIInsight.get_history(
        user_id=current_user.id,
        template_name=template_name,
        limit=limit
    )

    # Extract trend data points
    trends = {
        'dates': [],
        'portfolio_values': [],
        'position_counts': [],
        'tokens_used': []
    }

    for insight in reversed(history):  # Oldest first for charts
        trends['dates'].append(
            insight.generated_at.isoformat() if insight.generated_at else None
        )
        trends['portfolio_values'].append(
            float(insight.portfolio_value) if insight.portfolio_value else None
        )
        trends['position_counts'].append(insight.position_count)
        trends['tokens_used'].append(insight.tokens_used)

    return jsonify({
        'success': True,
        'data_points': len(history),
        'trends': trends
    })

