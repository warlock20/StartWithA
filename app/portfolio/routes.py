# StartWithA
# Copyright (C) 2024-2026 Kiran Mathews
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

# app/portfolio/routes.py

import logging
from decimal import Decimal
from flask import abort, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from app import db

# Configure logger
logger = logging.getLogger(__name__)
from app.models import (
    PortfolioPosition,
    Company,
    ThesisEvolution,
    BackgroundTask,
)
from app.services.currency_service import CurrencyService
from app.services.price_service import PriceService
from app.utils.time_utils import now_utc, ensure_timezone_aware
from app.utils.response_utils import json_error
from app.utils.decorators import require_feature
from app.utils.navigation_utils import get_smart_return_url
from app.services.background_tasks import BackgroundTaskService

from app.constants import (
    MAX_DYNAMIC_FORM_FIELDS,
)
from app.services.portfolio_intelligence import get_thesis_reality_check, get_return_target
from app.services.exit_watch import episodes as exit_episodes
from app.services.exit_watch import view as exit_watch_view
from app.services.portfolio_alerts import PortfolioAlertsService
from app.services.position_coverage import coverage_rows
from app.services.portfolio_analytics_metrics import build_portfolio_analytics
from app.services.portfolio_data_extractor import PortfolioDataExtractor
from app.services.decision_intelligence import (
    TABS, TAB_LABELS, DecisionIntelligenceService, normalise_tab,
)
from app.services.decision_quality import SCOPES
from app.services.research_effectiveness_actions import (
    FindingChanged, NoKillChecklist, mark_as_noise, status_message, suggest_from_finding,
)
from app.services.position_returns import holding_return_fields, position_returns
from app.services.expected_return import ExpectedReturnError, expected_return_from_form
from app.services.cash_service import CashService
from app.services.capital_timing import GRADUAL, LUMP_SUM, record_imported_capital
from app.services.portfolio_performance import PortfolioPerformanceService
from app.services.conviction_service import current_theses, conviction_summary

DECISION_TAB_TEMPLATES = {
    'insights': 'decisions/_tab_insights.html',
    'research': 'decisions/_tab_research.html',
    'decision-quality': 'decisions/_tab_decision_quality.html',
    'behaviour': 'decisions/_tab_behaviour.html',
}

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
        joinedload(PortfolioPosition.company).joinedload(Company.sector)
    ).all()

    # Portfolio totals from the single performance service (issue #336).
    # Reads cached DB data only — no API calls on the render path.
    portfolio_value = PortfolioPerformanceService.get_performance(current_user.id)

    # Identify stale positions for async refresh
    stale_company_ids = [
        pos.company_id for pos in positions
        if PriceService.should_update_price(pos)
    ]

    # Lifetime returns (unrealized + realized + dividends), one per position
    returns = position_returns(positions)
    gains_count = sum(1 for r in returns.values() if r.total_gain > 0)
    losses_count = sum(1 for r in returns.values() if r.total_gain < 0)

    # Get user currency settings
    user_currency = current_user.base_currency
    currency_symbol = CurrencyService.get_currency_symbol(user_currency)

    theses = current_theses(current_user.id, [pos.company_id for pos in positions])

    # Serialize positions for Tabulator + React dashboard island
    holdings_json = json.dumps([{
        'ticker': pos.company.ticker_symbol,
        'name': pos.company.name,
        'sector': pos.company.sector.display_name if pos.company.sector else (pos.company.industry or 'Uncategorized'),
        'shares': float(pos.total_shares) if pos.total_shares else 0,
        'avg_cost': float(round(pos.average_cost_basis_base or pos.average_cost_basis, 2)) if (pos.average_cost_basis_base or pos.average_cost_basis) else None,
        'current_price': float(round(pos.current_price_base, 2)) if pos.current_price_base else (float(round(pos.current_price, 2)) if pos.current_price else None),
        'current_value': float(round(pos.current_value)) if pos.current_value else None,
        'cost_basis': float(round(pos.total_cost)) if pos.total_cost else None,
        **holding_return_fields(returns.get(pos.company_id)),
        'total_dividends': float(pos.total_dividends or 0),
        'days_held': pos.days_held or 0,
        'company_id': pos.company_id,
        'position_url': url_for('companies.company_detail', company_id=pos.company_id),
        'add_tx_url': url_for('portfolio.add_transaction', company_id=pos.company_id),
        'conviction': theses[pos.company_id].conviction_level if pos.company_id in theses else None,
        'new_thesis_url': url_for('portfolio.add_thesis_version', company_id=pos.company_id),
    } for pos in positions])

    # Cash setup: infer initial deposit for existing users who haven't set up cash tracking
    inferred_deposit = None
    if not current_user.cash_setup_complete and portfolio_value['positions_count'] > 0:
        inferred_deposit = float(CashService.infer_initial_deposit(current_user.id))

    return render_template('portfolio_dashboard.html',
                          positions=positions,
                          holdings_json=holdings_json,
                          portfolio_value=portfolio_value,
                          portfolio_value_json=json.dumps({
                              k: float(v) if isinstance(v, Decimal) else v
                              for k, v in portfolio_value.items()
                          }),
                          gains_count=gains_count,
                          losses_count=losses_count,
                          stale_company_ids=json.dumps(stale_company_ids),
                          updated_time='just now',
                          currency_symbol=currency_symbol,
                          inferred_deposit=inferred_deposit,
                          conviction_summary=conviction_summary(positions, theses))


@portfolio_bp.route('/cash/setup', methods=['POST'])
@login_required
def cash_setup():
    """One-time initial capital confirmation for cash tracking."""
    amount = Decimal(request.form.get('initial_capital', '0'))
    if amount > 0:
        mode = request.form.get('capital_timing', GRADUAL)
        if mode not in (GRADUAL, LUMP_SUM):
            mode = GRADUAL
        record_imported_capital(current_user.id, amount, mode, current_user.base_currency)
    current_user.cash_setup_complete = True
    db.session.commit()
    flash('Initial capital recorded. Cash tracking is now active!', 'success')
    return redirect(url_for('portfolio.dashboard'))

############################
#### Postion Related ########
#############################

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
            try:
                expected = expected_return_from_form(request.form)
            except ExpectedReturnError as e:
                flash(str(e), 'error')
                return redirect(url_for('portfolio.add_thesis_version', company_id=company_id))
            expected_cagr = expected.cagr
            expected_timeframe = expected.timeframe_months
            if expected_timeframe is not None and expected_cagr is None:
                flash('Add the expected return that goes with the timeframe', 'error')
                return redirect(url_for('portfolio.add_thesis_version', company_id=company_id))

            key_metrics = {}
            if target_price:
                key_metrics['target_price'] = target_price
            if expected_cagr is not None:
                key_metrics['expected_cagr'] = expected_cagr
                if expected_timeframe:
                    key_metrics['expected_timeframe'] = expected_timeframe

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
            return redirect(url_for('companies.company_detail', company_id=company_id))

        except Exception:
            current_app.logger.exception('Error creating thesis version')
            db.session.rollback()
            flash('Error creating thesis version. Please try again.', 'error')
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

    stock_currency = company.reporting_currency or CurrencyService.detect_currency_from_ticker(company.ticker_symbol)
    currency_symbol = CurrencyService.get_currency_symbol(stock_currency)

    # Return target to prefill: the current version's, else the one set at purchase
    return_target = get_return_target(current_user.id, company_id)

    return render_template('add_thesis_version.html',
                          company=company,
                          position=position,
                          current_thesis=current_thesis,
                          return_target=return_target,
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

    except Exception:
        current_app.logger.exception('Error refreshing prices')
        flash('Error refreshing prices. Please try again.', 'error')

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
    A stored error payload (failed or insufficient-data run) counts as no result,
    so the panel shows its empty state with the Run button.
    """
    task = BackgroundTask.query.filter_by(
        user_id=user_id,
        task_type=f'portfolio_analysis:{template_name}',
        status='completed'
    ).order_by(BackgroundTask.completed_at.desc()).first()

    if task and task.result:
        result = json.loads(task.result)
        analysis = result.get('analysis')
        if analysis and analysis.get('metadata', {}).get('error'):
            return None
        return analysis
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
    Portfolio analytics: deterministic metrics computed from the user's own
    transactions (win rate, XIRR, hold times, sector allocation), plus the
    performance chart and the on-demand AI modules (sector momentum, tax).
    Nothing here calls an LLM; the modules run through /analytics/run.
    """
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

    return render_template('portfolio_basic_analytics.html',
                          metrics=build_portfolio_analytics(current_user.id),
                          chart_data=chart_data,
                          chart_task_id=chart_task_id,
                          selected_period=time_periods,
                          sector_momentum=sector_momentum,
                          tax_optimization=tax_optimization)


@portfolio_bp.route('/analytics/status/<task_id>')
@login_required
def analytics_status(task_id):
    """
    Check the status of a running portfolio analytics task.
    Returns JSON for AJAX polling from loading page.
    """
    task = BackgroundTaskService.owned_task(task_id, current_user.id)
    if not task:
        return jsonify({
            'state': 'NOT_FOUND',
            'current': 0,
            'total': 100,
            'status': 'Task not found',
            'error': 'Task ID not found in database'
        })

    response = BackgroundTaskService.legacy_poll_payload(task, {
        'pending': 'Task is waiting to start...',
        'running': 'Analysis in progress...',
        'completed': 'Analysis completed!',
        'failed': 'Analysis failed',
    })
    result = BackgroundTaskService.stored_result(task)
    if task.status == 'completed' and result:
        response['result'] = result
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
    """Decision Intelligence: one header, four tabs; only the requested tab is rendered."""
    tab = normalise_tab(request.args.get('tab'))
    service = DecisionIntelligenceService(current_user.id)
    # Smart back: wherever the user came from, else the intelligence hub
    return_url, context_label = get_smart_return_url('portfolio.intelligence_hub')
    return render_template('decisions_intelligence.html',
                           tab=tab,
                           tabs=TAB_LABELS,
                           tab_templates=DECISION_TAB_TEMPLATES,
                           header=service.header(),
                           panel=service.tab(tab),
                           effectiveness_status=status_message(current_user.id, request.args.get('re')),
                           return_url=return_url,
                           context_label=context_label)


@portfolio_bp.route('/analytics/decisions/panel/<tab>')
@login_required
def analytics_decisions_panel(tab):
    """One tab's HTML, fetched when the user opens a tab that was not rendered with the page."""
    template = DECISION_TAB_TEMPLATES.get(tab)
    if template is None:
        abort(404)
    return render_template(template, panel=DecisionIntelligenceService(current_user.id).tab(tab))


def _effectiveness_scope():
    """The scope of the panel the finding card was in; 'closed' when missing or unknown."""
    scope = request.form.get('scope', 'closed')
    return scope if scope in SCOPES else 'closed'


def _effectiveness_redirect(code):
    """Back to the section, which shows the result for ``code`` (see STATUS_MESSAGES)."""
    return redirect(url_for('portfolio.analytics_decisions', tab='research', re=code,
                            _anchor='research-effectiveness'))


@portfolio_bp.route('/analytics/decisions/effectiveness/suggest', methods=['POST'])
@login_required
def effectiveness_suggest():
    """Add a pending kill-checklist suggestion for a research effectiveness finding."""
    key = request.form.get('key', '')
    try:
        suggestion, created = suggest_from_finding(current_user.id, key, scope=_effectiveness_scope())
        db.session.commit()
    except FindingChanged:
        db.session.rollback()
        code = 'changed'
    except NoKillChecklist:
        db.session.rollback()
        code = 'no_kill_checklist'
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Research effectiveness suggestion failed for user %s', current_user.id)
        code = 'suggest_failed'
    else:
        # No suggestion back means the kill checklist already has the question
        code = 'added' if created else ('exists' if suggestion else 'already_in_checklist')
    return _effectiveness_redirect(code)


@portfolio_bp.route('/analytics/decisions/effectiveness/noise', methods=['POST'])
@login_required
def effectiveness_noise():
    """Hide a research effectiveness finding until its numbers change."""
    key = request.form.get('key', '')
    try:
        mark_as_noise(current_user.id, key, scope=_effectiveness_scope())
        db.session.commit()
    except FindingChanged:
        db.session.rollback()
        code = 'changed'
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Marking research effectiveness finding as noise failed for user %s',
                                     current_user.id)
        code = 'noise_failed'
    else:
        code = 'hidden'
    return _effectiveness_redirect(code)


@portfolio_bp.route('/analytics/research-correlation')
@login_required
def research_correlation():
    """Retired page; the research quality section on Decision Intelligence replaced it."""
    return redirect(url_for('portfolio.analytics_decisions', tab='research', _anchor='research-quality'),
                    code=301)


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
        'needs_attention': 0,
        'no_target': 0
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
    """Retired page: its content is the Your insights tab of Decision Intelligence (#442)."""
    return redirect(url_for('portfolio.analytics_decisions', tab='insights'), code=301)


@portfolio_bp.route('/intelligence')
@login_required
@require_feature('portfolio_intelligence')
def intelligence_hub():
    """
    Investment Intelligence Hub
    Central dashboard linking all intelligence features with summary metrics
    """
    # Exit-rule episodes first, committing only on a change, so the joinedloads below stay loaded
    if exit_episodes.resolve(current_user.id, now_utc()):
        db.session.commit()

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
    
    # Total return from the single performance service (issue #336) — measured
    # against capital invested, so it agrees with the portfolio dashboard.
    total_return = float(
        PortfolioPerformanceService.get_performance(current_user.id)['total_return_pct']
    )
    
    # Win rate and XIRR from the portfolio itself (closed positions / cash flows)
    summary = PortfolioDataExtractor(current_user.id).summary()
    closed_count = summary['wins'] + summary['losses']

    # Alerts, checkpoints, theses and coverage all come from one service so the
    # strip, the health bar and the cards agree (issue #435)
    alerts_service = PortfolioAlertsService(current_user.id)
    checkpoints_data = alerts_service.checkpoints_data
    checkpoint_summary = {
        'overdue_count': len(checkpoints_data.get('overdue', [])),
        'this_week_count': len(checkpoints_data.get('this_week', [])),
        'this_month_count': len(checkpoints_data.get('this_month', [])),
        'next_3_months_count': len(checkpoints_data.get('next_3_months', [])),
        'beyond_count': len(checkpoints_data.get('beyond', [])),
        'upcoming_count': len(checkpoints_data.get('this_month', [])) + len(checkpoints_data.get('next_3_months', [])),
        'total_active': sum(len(v) for v in checkpoints_data.values()),
        'needs_attention': len(checkpoints_data.get('overdue', [])) > 0
    }

    # Thesis reality
    thesis_positions = alerts_service.thesis_positions
    needs_attention = len([p for p in thesis_positions if p.status == 'needs_attention'])
    
    health = {
        'total_return': total_return,
        'xirr': summary['xirr'],
        'win_rate': summary['win_rate'] if closed_count else None,
        'wins': summary['wins'],
        'closed_count': closed_count,
        'overdue_checkpoints': checkpoint_summary.get('overdue_count', 0),
        'below_thesis': needs_attention,
        'no_exit_plan': alerts_service.coverage_counts()['no_exit_plan'],
    }
    
    alerts = alerts_service.strip_alerts()

    # ========================================
    # CARD DATA - Individual sections
    # ========================================
    
    # Returns (unrealized + realized + dividends) for open and closed positions
    all_positions = PortfolioPosition.query.filter_by(user_id=current_user.id).all()
    returns = position_returns(all_positions)

    # Performance Card (open positions), judged by the current holding: a trade
    # closed before a re-buy does not make today's holding a winner
    open_returns = [(p, returns[p.company_id]) for p in positions
                    if p.company_id in returns and returns[p.company_id].holding_return_pct is not None]
    winning_positions = sum(1 for _, r in open_returns if r.holding_return_pct > 0)
    losing_positions = sum(1 for _, r in open_returns if r.holding_return_pct < 0)

    top_performer = None
    if open_returns:
        best, best_return = max(open_returns, key=lambda pr: pr[1].holding_return_pct)
        if best.company:
            top_performer = {
                'ticker': best.company.ticker_symbol,
                'return': best_return.holding_return_pct
            }
    
    performance = {
        'has_data': len(positions) > 0,
        'total_return': total_return,
        'positions_count': len(positions),
        'winning': winning_positions,
        'losing': losing_positions,
        'top_performer': top_performer
    }
    
    # Decision Intelligence Card: the edge from the page's own header, the count from the same live cards
    di_service = DecisionIntelligenceService(current_user.id)
    di_insights = di_service.insights()
    di_card = {
        'research_edge': di_service.header()['research_edge'],
        'insights_count': None if di_insights['locked'] else len(di_insights['cards']),
        'closed_count': di_insights['closed_count'],
        'needed': di_insights['needed'],
        'links': [(TAB_LABELS[tab], url_for('portfolio.analytics_decisions', tab=tab)) for tab in TABS] + [
            ('Research effectiveness',
             url_for('portfolio.analytics_decisions', tab='research', _anchor='research-effectiveness')),
        ],
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
    
    rule_states = exit_watch_view.rule_states(
        current_user.id, [rule.id for row in alerts_service.coverage for rule in row.rules])

    return render_template('intelligence_hub.html',
                          health=health,
                          alerts=alerts,
                          coverage_rows=coverage_rows(alerts_service.coverage, rule_states),
                          performance=performance,
                          di_card=di_card,
                          checkpoints=checkpoints,
                          thesis=thesis)


#############################
#### Analytics History API  ####
#############################
