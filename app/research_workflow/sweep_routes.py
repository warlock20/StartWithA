"""
Market Sweep Routes — "Start with A's" feature.
Single-page experience for systematically screening all companies in a country.
"""

import logging

from flask import render_template, jsonify, request, current_app
from flask_login import current_user, login_required
from sqlalchemy import func

from app import db
from app.models import (
    MarketSweep, MarketSweepCompany, MarketSweepDecision,
    IdeaPipeline, Company, KillChecklist, KillCriterion, Sector,
    EmbeddingStore,
)
from app.research_workflow import research_workflow_bp
from app.services.currency_service import CurrencyService
from app.services.sector_service import SectorService
from app.services.ai.embedding_service import embed
from app.utils.time_utils import now_utc
from app.utils.response_utils import json_error

logger = logging.getLogger(__name__)


@research_workflow_bp.route('/start-with-A')
@login_required
def start_with_a():
    """Render the Start with A's single-page application."""
    sectors = Sector.query.filter_by(
        user_id=current_user.id, status='active'
    ).order_by(Sector.display_name).all()

    sectors_json = [{'id': s.id, 'name': s.display_name} for s in sectors]

    return render_template('start_with_a.html',
                           title="Start with A's",
                           sectors_json=sectors_json)


@research_workflow_bp.route('/api/sweeps')
@login_required
def list_sweeps():
    """List available market sweeps with user's progress stats."""
    sweeps = MarketSweep.query.filter_by(is_active=True).order_by(
        MarketSweep.created_at.desc()
    ).all()

    result = []
    for sweep in sweeps:
        decision_counts = db.session.query(
            MarketSweepDecision.decision, func.count(MarketSweepDecision.id)
        ).join(MarketSweepCompany).filter(
            MarketSweepCompany.sweep_id == sweep.id,
            MarketSweepDecision.user_id == current_user.id,
        ).group_by(MarketSweepDecision.decision).all()

        breakdown = dict(decision_counts)
        reviewed = sum(breakdown.values())

        result.append({
            'id': sweep.id,
            'name': sweep.name,
            'country': sweep.country,
            'description': sweep.description,
            'total_companies': sweep.total_companies,
            'reviewed': reviewed,
            'inbox_count': breakdown.get('inbox', 0),
            'killed_count': breakdown.get('killed', 0),
        })

    return jsonify({'success': True, 'sweeps': result})


@research_workflow_bp.route('/api/sweep/<int:sweep_id>/companies')
@login_required
def sweep_companies(sweep_id):
    """Get all companies in a sweep with user's existing decisions."""
    sweep = MarketSweep.query.get_or_404(sweep_id)

    rows = db.session.query(
        MarketSweepCompany, MarketSweepDecision
    ).outerjoin(
        MarketSweepDecision,
        db.and_(
            MarketSweepDecision.sweep_company_id == MarketSweepCompany.id,
            MarketSweepDecision.user_id == current_user.id,
        )
    ).filter(
        MarketSweepCompany.sweep_id == sweep_id
    ).order_by(MarketSweepCompany.sort_order).all()

    companies = []
    for company, decision in rows:
        companies.append({
            'id': company.id,
            'company_name': company.company_name,
            'ticker': company.ticker,
            'sector_label': company.sector_label,
            'market_cap': company.market_cap,
            'exchange': company.exchange,
            'sort_order': company.sort_order,
            'decision': decision.decision if decision else None,
            'decision_sector_id': decision.sector_id if decision else None,
            'decision_notes': decision.notes if decision else None,
            'promoted_idea_id': decision.promoted_idea_id if decision else None,
            'decided_at': decision.decided_at.isoformat() if decision and decision.decided_at else None,
        })

    return jsonify({
        'success': True,
        'sweep': {
            'id': sweep.id,
            'name': sweep.name,
            'country': sweep.country,
            'total_companies': sweep.total_companies,
        },
        'companies': companies,
    })


def _resolve_or_create_company(sweep_company, sector_id):
    """Find an existing Company for the current user or create one from the sweep row."""
    existing_company = None
    if sweep_company.ticker:
        existing_company = Company.query.filter(
            Company.user_id == current_user.id,
            Company.ticker_symbol == sweep_company.ticker,
        ).first()
    if not existing_company:
        existing_company = Company.query.filter(
            Company.user_id == current_user.id,
            func.lower(Company.name) == sweep_company.company_name.lower(),
        ).first()

    if existing_company:
        return existing_company.id

    sector_obj = None
    if sector_id:
        sector_obj = Sector.query.get(sector_id)
    elif sweep_company.sector_label:
        sector_obj = SectorService.find_or_create_sector(
            user_id=current_user.id,
            sector_name=sweep_company.sector_label,
            auto_create=True,
        )

    ticker = sweep_company.ticker or 'UNKNOWN'
    new_company = Company(
        user_id=current_user.id,
        name=sweep_company.company_name,
        ticker_symbol=ticker,
        sector_id=sector_obj.id if sector_obj else None,
        reporting_currency=CurrencyService.detect_currency_from_ticker(ticker) if ticker != 'UNKNOWN' else None,
    )
    db.session.add(new_company)
    db.session.flush()
    return new_company.id


def _summarize_checklist_kill(kill_reasons):
    """Build a human-readable kill_reason text from checklist results."""
    if not isinstance(kill_reasons, list) or not kill_reasons:
        return 'Checklist kill (no details)'
    failed = [r for r in kill_reasons if isinstance(r, dict) and r.get('result') == 'fail']
    total = len(kill_reasons)
    if not failed:
        return f'Checklist kill ({total} criteria evaluated)'
    questions = [r.get('question', '') for r in failed if r.get('question')]
    summary = f'Failed {len(failed)} of {total} criteria'
    if questions:
        summary += ': ' + '; '.join(questions)
    return summary


def _find_reusable_idea(existing_decision):
    """
    Return the IdeaPipeline row already linked to this decision if it is safe
    to mutate in place (i.e. still owned by the current user, auto-created by
    the market-sweep flow, and still in an early state). This lets us handle
    decision changes — e.g. Kill → Undo → Inbox — without orphaning rows or
    touching ideas that have been promoted into deeper research.
    """
    if not existing_decision or not existing_decision.promoted_idea_id:
        return None
    old_idea = IdeaPipeline.query.filter_by(
        id=existing_decision.promoted_idea_id,
        user_id=current_user.id,
    ).first()
    if (old_idea
            and old_idea.source == 'market_sweep'
            and old_idea.status in ('inbox', 'killed', 'survived')):
        return old_idea
    return None


def _clear_kill_embeddings(user_id, idea_id):
    """Remove any stale idea_kill embeddings for this idea (on re-kill or when
    a killed idea is re-decided to inbox/skip)."""
    EmbeddingStore.query.filter_by(
        user_id=user_id,
        entity_type='idea_kill',
        entity_id=idea_id,
    ).delete()


@research_workflow_bp.route('/api/sweep/decide', methods=['POST'])
@login_required
def sweep_decide():
    """Submit a decision for a market sweep company."""
    data = request.get_json()
    sweep_company_id = data.get('sweep_company_id')
    decision_type = data.get('decision')
    notes = data.get('notes')
    kill_reasons = data.get('kill_reasons')
    sector_id = data.get('sector_id')
    idea_status = data.get('idea_status', 'inbox')  # 'survived' when kill checklist passed
    kill_mode = data.get('kill_mode', 'checklist')  # 'checklist' or 'easy'
    kill_reason_text = (data.get('kill_reason_text') or '').strip()

    if not sweep_company_id or decision_type not in ('inbox', 'killed'):
        return json_error('Invalid parameters')

    if decision_type == 'killed' and kill_mode == 'easy' and not kill_reason_text:
        return json_error('Easy kill requires a reason')

    sweep_company = MarketSweepCompany.query.get_or_404(sweep_company_id)

    existing = MarketSweepDecision.query.filter_by(
        user_id=current_user.id,
        sweep_company_id=sweep_company_id,
    ).first()

    # If the user is changing a previous decision (e.g. Kill → Undo → Inbox),
    # reuse the existing IdeaPipeline row rather than orphaning it.
    reusable_idea = _find_reusable_idea(existing)

    promoted_idea_id = None

    if decision_type == 'inbox':
        company_id = _resolve_or_create_company(sweep_company, sector_id)

        # 'survived' = passed kill checklist → Ready state (skip kill room)
        pipeline_status = idea_status if idea_status in ('inbox', 'survived') else 'inbox'

        if reusable_idea:
            # Mutate in place so related rows (research projects, journal entries,
            # kill sessions) stay intact and no Too-Hard Basket orphan is left behind.
            _clear_kill_embeddings(current_user.id, reusable_idea.id)
            reusable_idea.status = pipeline_status
            reusable_idea.company_id = company_id
            reusable_idea.sector_id = sector_id
            reusable_idea.ticker_symbol = sweep_company.ticker
            reusable_idea.name = sweep_company.company_name
            reusable_idea.kill_reason = None
            reusable_idea.killed_at = None
            idea = reusable_idea
        else:
            idea = IdeaPipeline(
                user_id=current_user.id,
                name=sweep_company.company_name,
                idea_type='company',
                ticker_symbol=sweep_company.ticker,
                company_id=company_id,
                sector_id=sector_id,
                source='market_sweep',
                status=pipeline_status,
                created_at=now_utc(),
            )
            db.session.add(idea)

        db.session.flush()
        promoted_idea_id = idea.id

    elif decision_type == 'killed':
        # Create/update an IdeaPipeline row so the Too-Hard Basket picks this up
        company_id = _resolve_or_create_company(sweep_company, sector_id)

        if kill_mode == 'easy':
            computed_reason = kill_reason_text
            # For easy-kill, store a structured marker in kill_reasons so the UI/analytics can
            # distinguish it from checklist kills.
            kill_reasons = [{'mode': 'easy', 'reason': kill_reason_text}]
            if not notes:
                notes = kill_reason_text
        else:
            computed_reason = _summarize_checklist_kill(kill_reasons)

        if reusable_idea:
            # Re-kill or transition from inbox/survived → killed. Clear any previous
            # kill embedding before we (optionally) add a new one below.
            _clear_kill_embeddings(current_user.id, reusable_idea.id)
            reusable_idea.status = 'killed'
            reusable_idea.company_id = company_id
            reusable_idea.sector_id = sector_id
            reusable_idea.ticker_symbol = sweep_company.ticker
            reusable_idea.name = sweep_company.company_name
            reusable_idea.kill_reason = computed_reason
            reusable_idea.killed_at = now_utc()
            idea = reusable_idea
        else:
            idea = IdeaPipeline(
                user_id=current_user.id,
                name=sweep_company.company_name,
                idea_type='company',
                ticker_symbol=sweep_company.ticker,
                company_id=company_id,
                sector_id=sector_id,
                source='market_sweep',
                status='killed',
                kill_reason=computed_reason,
                killed_at=now_utc(),
                created_at=now_utc(),
            )
            db.session.add(idea)

        db.session.flush()
        promoted_idea_id = idea.id

        # Feed Argos: embed the free-text reason for semantic similarity matching.
        # Use a savepoint so a bad embedding never poisons the main commit.
        if kill_mode == 'easy' and kill_reason_text:
            try:
                vec = embed(kill_reason_text)
                if vec is not None:
                    try:
                        with db.session.begin_nested():
                            db.session.add(EmbeddingStore(
                                user_id=current_user.id,
                                entity_type='idea_kill',
                                entity_id=idea.id,
                                embedding_vector=vec.tolist(),
                                source_text=kill_reason_text[:500],
                                embedding_model='default',
                            ))
                    except Exception as e:
                        current_app.logger.warning(
                            f'Argos embedding save failed for idea {idea.id}: {e}'
                        )
            except Exception as e:
                current_app.logger.warning(
                    f'Argos embedding failed for kill idea {idea.id}: {e}'
                )

    # Upsert decision
    if existing:
        existing.decision = decision_type
        existing.notes = notes
        existing.kill_reasons = kill_reasons
        existing.sector_id = sector_id
        existing.promoted_idea_id = promoted_idea_id
        existing.decided_at = now_utc()
    else:
        db.session.add(MarketSweepDecision(
            user_id=current_user.id,
            sweep_company_id=sweep_company_id,
            decision=decision_type,
            notes=notes,
            kill_reasons=kill_reasons,
            sector_id=sector_id,
            promoted_idea_id=promoted_idea_id,
            decided_at=now_utc(),
        ))

    db.session.commit()

    return jsonify({
        'success': True,
        'decision': decision_type,
        'promoted_idea_id': promoted_idea_id,
    })


@research_workflow_bp.route('/api/sweep/undo', methods=['POST'])
@login_required
def sweep_undo():
    """Undo a decision for a market sweep company, deleting the decision row
    and cleaning up any auto-created IdeaPipeline / kill embeddings."""
    data = request.get_json()
    sweep_company_id = data.get('sweep_company_id')

    if not sweep_company_id:
        return json_error('Invalid parameters')

    existing = MarketSweepDecision.query.filter_by(
        user_id=current_user.id,
        sweep_company_id=sweep_company_id,
    ).first()

    if not existing:
        return jsonify({'success': True})  # nothing to undo

    # Clean up the promoted IdeaPipeline row if it was auto-created by the
    # sweep flow and hasn't been promoted into deeper research.
    reusable_idea = _find_reusable_idea(existing)
    if reusable_idea:
        _clear_kill_embeddings(current_user.id, reusable_idea.id)
        db.session.delete(reusable_idea)

    db.session.delete(existing)
    db.session.commit()

    return jsonify({'success': True})


@research_workflow_bp.route('/api/sweep/kill-checklist')
@login_required
def sweep_kill_checklist():
    """Get the user's default kill checklist criteria for the compact modal."""
    checklist = KillChecklist.query.filter_by(
        user_id=current_user.id,
        is_default=True,
    ).first()

    if not checklist:
        return jsonify({
            'success': True,
            'checklist': None,
            'criteria': [],
        })

    criteria = KillCriterion.query.filter_by(
        kill_checklist_id=checklist.id,
    ).order_by(KillCriterion.order).all()

    return jsonify({
        'success': True,
        'checklist': {'id': checklist.id, 'name': checklist.name},
        'criteria': [{
            'id': c.id,
            'question': c.question,
            'failure_reason': c.failure_reason,
            'help_text': c.help_text,
            'order': c.order,
        } for c in criteria],
    })
