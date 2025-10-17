from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user, login_required
from app import db
from app.models import (ResearchMetrics, IdeaPipeline, ResearchProject, 
                       DecisionJournal, ResearchLog, Company)
from app.analytics import analytics_bp
from app.analytics.utils import (update_user_metrics, analyze_idea_sources,
                                get_time_allocation_data, log_research_activity, KillSession)
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
                          confidence_trend=json.dumps(confidence_trend))

@analytics_bp.route('/decision-journal')
@login_required
def decision_journal_list():
    """List all investment decisions"""
    decisions = current_user.decision_journals.order_by(
        DecisionJournal.decision_date.desc()
    ).all()
    
    # Calculate statistics
    total_decisions = len(decisions)
    invest_decisions = sum(1 for d in decisions if d.decision_type == 'invest')
    pass_decisions = sum(1 for d in decisions if d.decision_type == 'pass')
    
    # Success tracking
    decisions_with_outcomes = [d for d in decisions if d.actual_return is not None]
    if decisions_with_outcomes:
        avg_return = sum(d.actual_return for d in decisions_with_outcomes) / len(decisions_with_outcomes)
        winning_trades = sum(1 for d in decisions_with_outcomes if d.actual_return > 0)
        win_rate = (winning_trades / len(decisions_with_outcomes)) * 100
    else:
        avg_return = 0
        win_rate = 0
    
    return render_template('decision_journal.html',
                          title="Decision Journal",
                          decisions=decisions,
                          total_decisions=total_decisions,
                          invest_decisions=invest_decisions,
                          pass_decisions=pass_decisions,
                          avg_return=round(avg_return, 1),
                          win_rate=round(win_rate, 1))

@analytics_bp.route('/decision-journal/new', methods=['GET', 'POST'])
@login_required
def new_decision():
    """Record a new investment decision"""
    if request.method == 'POST':
        company_id = request.form.get('company_id', type=int)
        decision_type = request.form.get('decision_type')
        confidence = request.form.get('confidence', type=int)
        thesis = request.form.get('investment_thesis')
        expected_return = request.form.get('expected_return', type=float)
        expected_timeframe = request.form.get('expected_timeframe', type=int)
        
        # Parse assumptions and risks
        assumptions = request.form.get('key_assumptions', '').split('\n')
        risks = request.form.get('biggest_risks', '').split('\n')
        
        decision = DecisionJournal(
            user=current_user,
            company_id=company_id,
            decision_type=decision_type,
            decision_date=now_utc().date(),
            confidence_score=confidence,
            investment_thesis=thesis,
            expected_return=expected_return,
            expected_timeframe=expected_timeframe,
            key_assumptions=[a.strip() for a in assumptions if a.strip()],
            biggest_risks=[r.strip() for r in risks if r.strip()],
            exit_criteria=request.form.get('exit_criteria')
        )
        
        # Link to project if exists
        project = ResearchProject.query.filter_by(
            user_id=current_user.id,
            company_id=company_id,
            status='completed'
        ).order_by(ResearchProject.completed_at.desc()).first()
        
        if project:
            decision.project_id = project.id
            # Update project decision if not set
            if not project.decision:
                project.decision = decision_type
                project.decision_confidence = confidence
                project.decision_date = now_utc()
        
        db.session.add(decision)
        
        # Log the activity
        log_research_activity(
            current_user.id,
            'decision_made',
            company_id=company_id,
            details={'decision': decision_type, 'confidence': confidence}
        )
        
        try:
            db.session.commit()
            flash('Investment decision recorded!', 'success')
            return redirect(url_for('analytics.decision_journal_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error recording decision: {str(e)}', 'error')
    
    # Get companies for dropdown
    companies = current_user.companies.order_by(Company.name).all()
    return render_template('new_decision.html',
                         title="Record Investment Decision",
                         companies=companies)

@analytics_bp.route('/decision-journal/<int:decision_id>/update', methods=['GET', 'POST'])
@login_required
def update_decision_outcome(decision_id):
   """Update the outcome of an investment decision"""
   decision = DecisionJournal.query.get_or_404(decision_id)
   
   if decision.user_id != current_user.id:
       flash('Access denied', 'error')
       return redirect(url_for('analytics.decision_journal_list'))
   
   if request.method == 'POST':
       decision.actual_return = request.form.get('actual_return', type=float)
       decision.actual_timeframe = request.form.get('actual_timeframe', type=int)
       decision.outcome_date = datetime.strptime(request.form.get('outcome_date'), '%Y-%m-%d').date()
       decision.outcome_notes = request.form.get('outcome_notes')
       decision.what_went_right = request.form.get('what_went_right')
       decision.what_went_wrong = request.form.get('what_went_wrong')
       decision.lessons_learned = request.form.get('lessons_learned')
       decision.would_repeat = request.form.get('would_repeat') == 'true'
       decision.mistake_category = request.form.get('mistake_category')
       decision.success_category = request.form.get('success_category')
       decision.updated_at = now_utc()
       
       try:
           db.session.commit()
           if decision.actual_return is not None and not decision.postmortem:
               flash('Consider creating a postmortem for this investment to capture learnings', 'info')
               
           # Update user metrics
           update_user_metrics(current_user.id)
           
           flash('Decision outcome updated!', 'success')
           return redirect(url_for('analytics.decision_journal_list'))
       except Exception as e:
           db.session.rollback()
           flash(f'Error updating outcome: {str(e)}', 'error')
   
   return render_template('update_decision.html',
                         title="Update Decision Outcome",
                         decision=decision)

@analytics_bp.route('/export-data')
@login_required
def export_data():
   """Export analytics data for external analysis"""
   # This would generate a CSV or JSON export of the user's data
   # Implementation depends on specific needs
   flash('Data export feature coming soon!', 'info')
   return redirect(url_for('analytics.dashboard'))