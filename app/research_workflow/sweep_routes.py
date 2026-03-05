"""
Market Sweep Routes — "Start with A's" feature.
Single-page experience for systematically screening all companies in a country.
"""

import logging

from flask import render_template, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import func

from app import db
from app.models import (
    MarketSweep, MarketSweepCompany, MarketSweepDecision,
    IdeaPipeline, Company, KillChecklist, KillCriterion, Sector,
)
from app.research_workflow import research_workflow_bp
from app.services.sector_service import SectorService
from app.utils.time_utils import now_utc

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
            'skip_count': breakdown.get('skip', 0),
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

    if not sweep_company_id or decision_type not in ('skip', 'inbox', 'killed'):
        return jsonify({'success': False, 'error': 'Invalid parameters'}), 400

    sweep_company = MarketSweepCompany.query.get_or_404(sweep_company_id)

    existing = MarketSweepDecision.query.filter_by(
        user_id=current_user.id,
        sweep_company_id=sweep_company_id,
    ).first()

    promoted_idea_id = None

    if decision_type == 'inbox':
        # Find or create Company record
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

        if not existing_company:
            sector_obj = None
            if sector_id:
                sector_obj = Sector.query.get(sector_id)
            elif sweep_company.sector_label:
                sector_obj = SectorService.find_or_create_sector(
                    user_id=current_user.id,
                    sector_name=sweep_company.sector_label,
                    auto_create=True,
                )

            new_company = Company(
                user_id=current_user.id,
                name=sweep_company.company_name,
                ticker_symbol=sweep_company.ticker or 'UNKNOWN',
                sector_id=sector_obj.id if sector_obj else None,
            )
            db.session.add(new_company)
            db.session.flush()
            company_id = new_company.id
        else:
            company_id = existing_company.id

        # Create IdeaPipeline record
        # 'survived' = passed kill checklist → Ready state (skip kill room)
        pipeline_status = idea_status if idea_status in ('inbox', 'survived') else 'inbox'
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
