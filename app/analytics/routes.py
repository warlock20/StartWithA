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

from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload
from app import db, limiter
from app.models import (ResearchMetrics, IdeaPipeline, ResearchProject,
                       DecisionJournal, ResearchLog, Company, KillSession,
                       BackgroundTask)
from app.models.idea_pipeline import KillCriterion
from app.analytics import analytics_bp
from app.analytics.utils import (update_user_metrics, analyze_idea_sources,
                                get_time_allocation_data, log_research_activity)
from app.services.too_hard_service import TooHardBasketService
from app.services.background_tasks import BackgroundTaskService
from app.services.screening_analysis_service import ScreeningAnalysisService
from app.services.ai.prompt_service import prompt_service
from app.constants import RATELIMIT_AI
from datetime import datetime, timedelta
from app.utils.time_utils import now_utc, ensure_timezone_aware
import json
import logging

logger = logging.getLogger(__name__)

@analytics_bp.route('/dashboard')
@login_required
def dashboard():
    """Main analytics dashboard — Insights, Initial Screening, Circle of Competence"""
    # Update metrics
    metrics = update_user_metrics(current_user.id)

    # ── Insights tab: Kill Patterns ──
    kill_sessions = KillSession.query.filter_by(user_id=current_user.id)\
        .options(joinedload(KillSession.idea)).all()

    criterion_ids = {
        s.idea.failed_criterion_id for s in kill_sessions
        if s.idea and s.idea.failed_criterion_id
    }
    criteria_map = {}
    if criterion_ids:
        criteria_map = {
            c.id: c.question for c in KillCriterion.query.filter(
                KillCriterion.id.in_(criterion_ids)
            ).all()
        }

    kill_criteria_stats = {}
    for session in kill_sessions:
        if session.idea and session.idea.failed_criterion_id:
            question = criteria_map.get(session.idea.failed_criterion_id)
            if question:
                kill_criteria_stats[question] = kill_criteria_stats.get(question, 0) + 1

    top_kill_reasons = sorted(kill_criteria_stats.items(),
                            key=lambda x: x[1], reverse=True)[:10]

    # Kill stages breakdown
    kill_screening_count = sum(
        1 for s in kill_sessions
        if s.idea and s.idea.status == 'killed'
    )
    research_kills_count = ResearchProject.query.filter_by(
        user_id=current_user.id, status='killed'
    ).count()

    kill_stages = []
    if kill_screening_count > 0:
        kill_stages.append({'name': 'Kill Checklist', 'count': kill_screening_count})
    if research_kills_count > 0:
        kill_stages.append({'name': 'Research', 'count': research_kills_count})

    total_kills = kill_screening_count + research_kills_count

    # ── Insights tab: Research Velocity ──
    twelve_months_ago = now_utc() - timedelta(days=360)

    project_dates = [
        ensure_timezone_aware(r[0]) for r in db.session.query(ResearchProject.completed_at)
        .filter(
            ResearchProject.user_id == current_user.id,
            ResearchProject.completed_at >= twelve_months_ago,
            ResearchProject.completed_at.isnot(None)
        ).all()
    ]
    idea_dates = [
        ensure_timezone_aware(r[0]) for r in db.session.query(IdeaPipeline.created_at)
        .filter(
            IdeaPipeline.user_id == current_user.id,
            IdeaPipeline.created_at >= twelve_months_ago
        ).all()
    ]

    velocity_data = []
    for i in range(12):
        start_date = now_utc() - timedelta(days=(i+1)*30)
        end_date = now_utc() - timedelta(days=i*30)
        velocity_data.append({
            'month': end_date.strftime('%b'),
            'started': sum(1 for d in idea_dates if start_date <= d < end_date),
            'completed': sum(1 for d in project_dates if start_date <= d < end_date)
        })
    velocity_data.reverse()

    # ── Insights tab: Idea Sources ──
    source_analyses = analyze_idea_sources(current_user.id)
    sources_sorted = sorted(source_analyses, key=lambda x: x.total_ideas, reverse=True)[:10]
    sources_simple = [
        {'source': s.source_name[:30], 'count': s.total_ideas}
        for s in sources_sorted
    ]
    sources_total = sum(s.total_ideas for s in sources_sorted)

    # ── Insights tab: Research Efficiency ──
    total_projects = ResearchProject.query.filter_by(
        user_id=current_user.id
    ).count()
    projects_decided = ResearchProject.query.filter_by(
        user_id=current_user.id
    ).filter(ResearchProject.decision.isnot(None)).count()
    projects_invested = ResearchProject.query.filter_by(
        user_id=current_user.id, decision='invest'
    ).count()
    projects_passed = ResearchProject.query.filter_by(
        user_id=current_user.id, decision='pass'
    ).count()

    completion_rate = round(projects_decided / total_projects * 100) if total_projects > 0 else 0
    total_decisions = projects_invested + projects_passed
    selectivity = round(projects_invested / total_decisions * 100) if total_decisions > 0 else 0
    avg_days = round(metrics.average_days_to_decision) if metrics and metrics.average_days_to_decision else 0
    efficiency_detail = (
        f"{projects_decided} of {total_projects} projects reached a decision"
        f" — {projects_invested} invested, {projects_passed} passed"
        f", {research_kills_count} killed early"
    ) if total_projects > 0 else "No projects yet"

    # ── Circle of Competence tab ──
    coc_analytics_data = TooHardBasketService.get_analytics(current_user.id)
    sector_stats = coc_analytics_data.get('sector_stats', {})

    coc_sector_data = []
    for sector_name, stats in sorted(sector_stats.items(),
                                     key=lambda x: x[1].get('total_analyzed', 0),
                                     reverse=True)[:10]:
        coc_sector_data.append({
            'name': sector_name,
            'count': stats.get('total_analyzed', 0),
            'confidence': round(stats.get('coc_confidence', 0), 1),
        })

    # Sorted by confidence for ranking list
    coc_sectors_ranked = sorted(coc_sector_data, key=lambda x: x['confidence'], reverse=True)

    # Count sectors with assessments
    sectors_assessed = sum(1 for s in coc_sector_data if s['confidence'] > 0)
    sectors_total = len(coc_sector_data)

    return render_template('analytics_dashboard.html',
                          title="Analytics",
                          metrics=metrics,
                          # Insights — Kill Patterns
                          top_kill_reasons=top_kill_reasons,
                          kill_stages=kill_stages,
                          total_kills=total_kills,
                          # Insights — Velocity
                          velocity_data=json.dumps(velocity_data),
                          # Insights — Sources
                          sources_simple=json.dumps(sources_simple),
                          sources_total=sources_total,
                          # Insights — Efficiency
                          completion_rate=completion_rate,
                          avg_days=avg_days,
                          selectivity=selectivity,
                          efficiency_detail=efficiency_detail,
                          # Circle of Competence
                          sector_donut_data=json.dumps(coc_sector_data),
                          coc_sectors_ranked=coc_sectors_ranked,
                          sectors_total=sectors_total,
                          sectors_assessed=sectors_assessed)


# ── Screening Analysis API ──────────────────────────────────────────────────


@analytics_bp.route('/api/screening-analysis', methods=['POST'])
@login_required
@limiter.limit(RATELIMIT_AI)
def run_screening_analysis():
    """
    Start AI-powered screening analysis of kill checklist history.

    Returns task_id for polling.
    """
    # 1. Check sufficient data
    can_analyze, stats = ScreeningAnalysisService.has_sufficient_data(current_user.id)
    if not can_analyze:
        return jsonify({
            'success': False,
            'error': (
                f"Insufficient data. Found {stats['completed_sessions']} completed "
                f"sessions, minimum is {stats['minimum_required']}."
            ),
            'stats': stats
        }), 400

    # 2. Token quota check (estimate from prompt YAML config)
    prompt_info = prompt_service.get_prompt_info('screening', 'screening_analysis')
    estimated_tokens = prompt_info['max_tokens']

    if not current_user.can_use_ai_tokens(estimated_tokens):
        return jsonify({
            'success': False,
            'error': f'Token limit reached. Used {current_user.ai_tokens_used:,} of {current_user.ai_tokens_limit:,}'
        }), 429

    # 3. Start background task
    task_id = BackgroundTaskService.start_screening_analysis(current_user.id)

    logger.info(f"Started screening analysis task {task_id} for user {current_user.id}")

    return jsonify({
        'success': True,
        'task_id': task_id,
        'message': 'Screening analysis started'
    })


@analytics_bp.route('/api/screening-analysis/status/<task_id>')
@login_required
def get_screening_analysis_status(task_id):
    """
    Poll screening analysis task status.

    Returns state and result when completed.
    """
    task = BackgroundTask.query.get(task_id)

    if not task or task.user_id != current_user.id:
        return jsonify({'state': 'NOT_FOUND'}), 404

    response = {
        'state': task.status.upper(),
        'current': {'pending': 10, 'running': 50, 'completed': 100, 'failed': 0}.get(task.status, 0),
        'total': 100
    }

    if task.status == 'completed' and task.result:
        response['result'] = json.loads(task.result)

    elif task.status == 'failed':
        response['error'] = task.error_message or 'Analysis failed'

    return jsonify(response)


@analytics_bp.route('/api/screening-analysis/latest')
@login_required
def get_latest_screening_analysis():
    """
    Get the most recent completed screening analysis for the current user.

    Returns the stored result JSON or has_result=false if none exists.
    """
    task = BackgroundTask.query.filter_by(
        user_id=current_user.id,
        task_type='screening_analysis',
        status='completed'
    ).order_by(BackgroundTask.completed_at.desc()).first()

    if task and task.result:
        return jsonify({
            'success': True,
            'has_result': True,
            'result': json.loads(task.result),
            'analyzed_at': task.completed_at.isoformat() if task.completed_at else None
        })

    return jsonify({
        'success': True,
        'has_result': False
    })