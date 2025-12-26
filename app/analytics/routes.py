from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user, login_required
from app import db
from app.models import (ResearchMetrics, IdeaPipeline, ResearchProject,
                       DecisionJournal, ResearchLog, Company)
from app.models.sector import SectorAnalysis
from app.analytics import analytics_bp
from app.analytics.utils import (update_user_metrics, analyze_idea_sources,
                                get_time_allocation_data, log_research_activity, KillSession)
from app.services.too_hard_service import TooHardBasketService
from app.services.sector_service import SectorService
from datetime import datetime, timedelta
from app.utils.time_utils import now_utc
import json

@analytics_bp.route('/dashboard')
@login_required
def dashboard():
    """Main analytics dashboard with all tabs"""
    # Update metrics first
    metrics = update_user_metrics(current_user.id)

    # Get time allocation for last 30 days
    time_data = get_time_allocation_data(current_user.id, days=30)

    # Get recent activity
    recent_logs = current_user.research_logs.order_by(
        ResearchLog.timestamp.desc()
    ).limit(10).all()

    # Calculate success rates
    success_rate = 0
    if metrics and metrics.total_investment_decisions > 0:
        success_rate = (metrics.invest_decisions / metrics.total_investment_decisions) * 100

    # Get idea source quality
    source_analyses = analyze_idea_sources(current_user.id)
    best_sources = sorted(source_analyses,
                         key=lambda x: x.survival_rate or 0,
                         reverse=True)[:5]
    by_survival = sorted(source_analyses, key=lambda x: x.survival_rate or 0, reverse=True)
    by_investment = sorted(source_analyses, key=lambda x: x.investment_rate or 0, reverse=True)

    # Prepare chart data for Overview tab
    time_by_day_chart = []
    if time_data['by_day']:
        sorted_days = sorted(time_data['by_day'].items())
        for day, minutes in sorted_days[-30:]:  # Last 30 days
            time_by_day_chart.append({
                'date': day.strftime('%Y-%m-%d'),
                'hours': round(minutes / 60, 1)
            })

    # Prepare chart data for Time Analysis tab
    step_chart_data = []
    if time_data['by_type']:
        for step, minutes in sorted(time_data['by_type'].items(),
                                   key=lambda x: x[1], reverse=True)[:10]:
            step_chart_data.append({
                'step': step,
                'hours': round(minutes / 60, 1)
            })

    company_chart_data = []
    if time_data['by_company']:
        for company, minutes in sorted(time_data['by_company'].items(),
                                      key=lambda x: x[1], reverse=True)[:10]:
            company_chart_data.append({
                'company': company,
                'hours': round(minutes / 60, 1)
            })

    # Productivity patterns
    productivity_by_hour = {}
    productivity_by_day = {}
    recent_logs_30d = current_user.research_logs.filter(
        ResearchLog.timestamp >= now_utc() - timedelta(days=30)
    ).all()
    for log in recent_logs_30d:
        if log.hour_of_day is not None:
            productivity_by_hour[log.hour_of_day] = \
                productivity_by_hour.get(log.hour_of_day, 0) + 1
        if log.day_of_week is not None:
            productivity_by_day[log.day_of_week] = \
                productivity_by_day.get(log.day_of_week, 0) + 1

    # Prepare chart data for Idea Sources tab
    source_chart_data = []
    for source in source_analyses[:10]:
        source_chart_data.append({
            'source': source.source_name[:30],
            'total': source.total_ideas,
            'killed': source.ideas_killed,
            'promoted': source.ideas_promoted,
            'invested': source.ideas_invested
        })

    # Prepare data for Research Patterns tab
    kill_criteria_stats = {}
    kill_sessions = KillSession.query.filter_by(user_id=current_user.id).all()
    for session in kill_sessions:
        if session.idea and session.idea.failed_criterion_id:
            criterion = session.checklist.criteria.filter_by(
                id=session.idea.failed_criterion_id
            ).first()
            if criterion:
                question = criterion.question
                kill_criteria_stats[question] = kill_criteria_stats.get(question, 0) + 1

    top_kill_reasons = sorted(kill_criteria_stats.items(),
                            key=lambda x: x[1], reverse=True)[:10]

    # Research velocity
    velocity_data = []
    for i in range(12):
        start_date = now_utc() - timedelta(days=(i+1)*30)
        end_date = now_utc() - timedelta(days=i*30)

        projects_completed = ResearchProject.query.filter(
            ResearchProject.user_id == current_user.id,
            ResearchProject.completed_at >= start_date,
            ResearchProject.completed_at < end_date
        ).count()

        ideas_processed = IdeaPipeline.query.filter(
            IdeaPipeline.user_id == current_user.id,
            IdeaPipeline.created_at >= start_date,
            IdeaPipeline.created_at < end_date
        ).count()

        velocity_data.append({
            'month': end_date.strftime('%b %Y'),
            'projects': projects_completed,
            'ideas': ideas_processed
        })

    velocity_data.reverse()

    # Confidence trend
    decisions = current_user.decision_journals.filter(
        DecisionJournal.confidence_score.isnot(None)
    ).order_by(DecisionJournal.decision_date).all()

    confidence_trend = []
    for decision in decisions:
        confidence_trend.append({
            'date': decision.decision_date.strftime('%Y-%m-%d'),
            'confidence': decision.confidence_score,
            'type': decision.decision_type,
            'company': decision.company.name if decision.company else 'Unknown'
        })

    # Get Circle of Competence analytics data
    coc_analytics_data = TooHardBasketService.get_analytics(current_user.id)
    sector_analytics_dict = SectorService.get_sector_analytics(current_user.id)

    # Categorize sectors by competence level
    sectors_by_competence = {
        'expert': [],
        'proficient': [],
        'developing': [],
        'novice': []
    }

    # Extract the list of all sectors from the analytics dictionary
    all_sectors = sector_analytics_dict.get('all', []) if isinstance(sector_analytics_dict, dict) else []

    # Filter to only include sectors with actual research content
    if all_sectors:
        filtered_sectors = []
        for sector in all_sectors:
            # Get the SectorAnalysis for this sector to check for content
            analysis = SectorAnalysis.query.filter_by(
                user_id=current_user.id,
                sector_id=sector.id
            ).first()

            if analysis:
                # Check if sector has meaningful content:
                # - Documentation/canvas notes (word_count)
                # - Research sources
                # - Questions in question bank
                # - Time spent researching
                # - Companies analyzed
                has_content = (
                    analysis.word_count > 0 or
                    analysis.sources_count > 0 or
                    analysis.questions_count > 0 or
                    analysis.total_time_spent > 0 or
                    sector.companies_analyzed > 0
                )

                if has_content:
                    filtered_sectors.append(sector)

        all_sectors = filtered_sectors

    if all_sectors:
        for sector in all_sectors:
            competence_dict = sector.competence_level
            level_name = competence_dict.get('level', 'novice') if isinstance(competence_dict, dict) else 'novice'

            sector_data = {
                'id': sector.id,
                'name': sector.display_name,
                'slug': sector.slug,
                'coc_confidence': round(sector.coc_confidence, 1),
                'success_rate': round(sector.success_rate, 1) if sector.success_rate else 0,
                'companies_analyzed': sector.companies_analyzed,
                'companies_invested': sector.companies_invested,
                'total_hours': round(sector.total_research_hours, 1) if sector.total_research_hours else 0,
                'coc_yes_count': sector.coc_yes_count,
                'coc_no_count': sector.coc_no_count,
                'coc_unsure_count': sector.coc_unsure_count,
                'competence_level': competence_dict.get('label', 'Novice') if isinstance(competence_dict, dict) else 'Novice'
            }

            if level_name in sectors_by_competence:
                sectors_by_competence[level_name].append(sector_data)
            else:
                sectors_by_competence['novice'].append(sector_data)

    # Prepare CoC breakdown
    coc_stats = coc_analytics_data.get('coc_stats', {'yes': 0, 'no': 0, 'unsure': 0})
    coc_breakdown = {
        'yes': coc_stats.get('yes', 0),
        'no': coc_stats.get('no', 0),
        'unsure': coc_stats.get('unsure', 0)
    }

    # Get CoC recommendations
    coc_recommendations = coc_analytics_data.get('recommendations', [])

    # Prepare sector chart data
    sector_stats = coc_analytics_data.get('sector_stats', {})
    coc_sector_chart_data = []
    for sector_name, stats in sorted(sector_stats.items(),
                                     key=lambda x: x[1].get('total_analyzed', 0),
                                     reverse=True)[:10]:
        coc_sector_chart_data.append({
            'name': sector_name,
            'total_analyzed': stats.get('total_analyzed', 0),
            'invested': stats.get('invested', 0),
            'killed': stats.get('killed', 0),
            'abandoned': stats.get('abandoned', 0),
            'passed_full': stats.get('passed_full', 0),
            'total_time': round(stats.get('total_time', 0), 1),
            'coc_confidence': round(stats.get('coc_confidence', 0), 1),
            'success_rate': round(stats.get('success_rate', 0), 1)
        })

    # Calculate CoC summary stats
    coc_total_companies = sum(s['total_analyzed'] for s in coc_sector_chart_data)
    coc_total_hours = sum(s['total_time'] for s in coc_sector_chart_data)
    coc_total_within = coc_breakdown['yes']
    coc_total_outside = coc_breakdown['no']
    coc_total_unsure = coc_breakdown['unsure']
    coc_total_assessed = coc_total_within + coc_total_outside + coc_total_unsure
    coc_overall_confidence = (coc_total_within / coc_total_assessed * 100) if coc_total_assessed > 0 else 0

    return render_template('analytics_dashboard.html',
                          title="Research Analytics",
                          metrics=metrics,
                          time_data=time_data,
                          recent_logs=recent_logs,
                          success_rate=round(success_rate, 1),
                          best_sources=best_sources,
                          source_analyses=source_analyses,
                          by_survival=by_survival,
                          by_investment=by_investment,
                          time_by_day_chart=json.dumps(time_by_day_chart),
                          step_chart_data=json.dumps(step_chart_data),
                          company_chart_data=json.dumps(company_chart_data),
                          productivity_by_hour=productivity_by_hour,
                          productivity_by_day=productivity_by_day,
                          source_chart_data=json.dumps(source_chart_data),
                          top_kill_reasons=top_kill_reasons,
                          velocity_data=json.dumps(velocity_data),
                          confidence_trend=json.dumps(confidence_trend),
                          coc_breakdown=coc_breakdown,
                          sectors_by_competence=sectors_by_competence,
                          coc_recommendations=coc_recommendations,
                          coc_sector_chart_data=json.dumps(coc_sector_chart_data),
                          coc_total_companies=coc_total_companies,
                          coc_total_hours=round(coc_total_hours, 1),
                          coc_total_within=coc_total_within,
                          coc_total_outside=coc_total_outside,
                          coc_total_unsure=coc_total_unsure,
                          coc_total_assessed=coc_total_assessed,
                          coc_overall_confidence=round(coc_overall_confidence, 1))