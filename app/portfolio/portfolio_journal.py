import logging
from flask import  request, render_template, flash, redirect, url_for
from flask_login import login_required, current_user

from app import db
from app.portfolio import portfolio_bp
from app.models import DecisionJournal, Transaction, PortfolioPosition, ResearchProject
from app.constants import JOURNALS_PER_PAGE
from app.utils.time_utils import now_utc

logger = logging.getLogger(__name__)

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

    # Get portfolio position for auto-calculated return
    position = PortfolioPosition.query.filter_by(
        user_id=current_user.id,
        company_id=journal.company_id
    ).first()
    calculated_return = None
    if position and position.realized_gain_loss_pct is not None:
        calculated_return = float(position.realized_gain_loss_pct)

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
                          buy_journal=buy_journal,
                          calculated_return=calculated_return)

