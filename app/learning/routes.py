from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user, login_required
from app import db
from app.models import (MistakeLog, WeeklyReview, InvestmentPostMortem,
                       PatternRecognition, LearningPath, DecisionJournal,
                       Company, LearningNote, Sector, SectorAnalysis)
from app.learning import learning_bp
from app.learning.utils import (get_weekly_metrics, identify_patterns,
                               calculate_learning_score, get_review_schedule,
                               generate_learning_recommendations)
from app.utils.time_utils import now_utc, ensure_timezone_aware
from datetime import datetime, timedelta, date

@learning_bp.route('/dashboard')
@login_required
def learning_dashboard():
    """Main learning dashboard"""
    # Calculate learning score (internal use - not displayed)
    learning_score = calculate_learning_score(current_user.id)

    # Get curated wisdom stats
    total_insights = LearningNote.query.filter_by(user_id=current_user.id).count()

    # Get last reviewed date (most recent)
    last_reviewed_insight = LearningNote.query.filter_by(user_id=current_user.id)\
        .filter(LearningNote.last_reviewed.isnot(None))\
        .order_by(LearningNote.last_reviewed.desc())\
        .first()

    last_reviewed_date = ensure_timezone_aware(last_reviewed_insight.last_reviewed) if last_reviewed_insight else None

    # Count stale insights (not reviewed in 30+ days or never reviewed)
    thirty_days_ago = now_utc() - timedelta(days=30)
    stale_insights = LearningNote.query.filter_by(user_id=current_user.id).filter(
        db.or_(
            LearningNote.last_reviewed.is_(None),
            LearningNote.last_reviewed < thirty_days_ago
        )
    ).count()

    curated_wisdom_stats = {
        'total': total_insights,
        'last_reviewed': last_reviewed_date,
        'stale_count': stale_insights
    }

    # Get sector knowledge stats (count active research notebooks with continuous learning enabled)
    total_sectors = SectorAnalysis.query.filter_by(
        user_id=current_user.id,
        status='active',
        continuous_learning_enabled=True
    ).count()

    # Get last researched from sector with active analysis and continuous learning enabled
    last_researched_sector = db.session.query(Sector)\
        .join(SectorAnalysis, Sector.id == SectorAnalysis.sector_id)\
        .filter(
            SectorAnalysis.user_id == current_user.id,
            SectorAnalysis.status == 'active',
            SectorAnalysis.continuous_learning_enabled == True
        )\
        .filter(Sector.last_researched.isnot(None))\
        .order_by(Sector.last_researched.desc())\
        .first()

    last_researched_date = ensure_timezone_aware(last_researched_sector.last_researched) if last_researched_sector else None

    # Count stale sectors (with active analysis and continuous learning enabled)
    stale_sectors = db.session.query(Sector)\
        .join(SectorAnalysis, Sector.id == SectorAnalysis.sector_id)\
        .filter(
            SectorAnalysis.user_id == current_user.id,
            SectorAnalysis.status == 'active',
            SectorAnalysis.continuous_learning_enabled == True
        )\
        .filter(
            db.or_(
                Sector.last_researched.is_(None),
                Sector.last_researched < thirty_days_ago
            )
        ).count()

    sector_knowledge_stats = {
        'total': total_sectors,
        'last_researched': last_researched_date,
        'stale_count': stale_sectors
    }

    # Get review schedule
    review_schedule = get_review_schedule(current_user.id)

    # Get recent mistakes
    recent_mistakes = current_user.mistake_logs.order_by(
        MistakeLog.created_at.desc()
    ).limit(5).all()

    # Get learning recommendations
    recommendations = generate_learning_recommendations(current_user.id)

    # Get active learning paths
    active_paths = current_user.learning_paths.filter_by(status='active').all()

    # Get recent patterns
    recent_patterns = current_user.patterns.order_by(
        PatternRecognition.identified_date.desc()
    ).limit(5).all()

    # Calculate improvement metrics
    today = now_utc().date()
    recent_decisions = current_user.decision_journals.filter(
        DecisionJournal.decision_date >= today - timedelta(days=90)
    ).all()

    older_decisions = current_user.decision_journals.filter(
        DecisionJournal.decision_date < today - timedelta(days=90),
        DecisionJournal.decision_date >= today - timedelta(days=180)
    ).all()

    improvement_data = {
        'recent_confidence': 0,
        'older_confidence': 0,
        'confidence_trend': 'stable'
    }

    if recent_decisions:
        recent_confidence = sum(d.confidence_score or 0 for d in recent_decisions) / len(recent_decisions)
        improvement_data['recent_confidence'] = round(recent_confidence, 1)

    if older_decisions:
        older_confidence = sum(d.confidence_score or 0 for d in older_decisions) / len(older_decisions)
        improvement_data['older_confidence'] = round(older_confidence, 1)

    if improvement_data['recent_confidence'] and improvement_data['older_confidence']:
        if improvement_data['recent_confidence'] > improvement_data['older_confidence']:
            improvement_data['confidence_trend'] = 'improving'
        elif improvement_data['recent_confidence'] < improvement_data['older_confidence']:
            improvement_data['confidence_trend'] = 'declining'

    return render_template('learning_dashboard.html',
                          title="Learning Center",
                          learning_score=learning_score,
                          curated_wisdom_stats=curated_wisdom_stats,
                          sector_knowledge_stats=sector_knowledge_stats,
                          review_schedule=review_schedule,
                          recent_mistakes=recent_mistakes,
                          recommendations=recommendations,
                          active_paths=active_paths,
                          recent_patterns=recent_patterns,
                          improvement_data=improvement_data,
                          now=now_utc())

@learning_bp.route('/mistakes')
@login_required
def mistake_log():
    """View and manage mistake log"""
    mistakes = current_user.mistake_logs.order_by(
        MistakeLog.created_at.desc()
    ).all()
    
    # Categorize mistakes
    by_type = {}
    for mistake in mistakes:
        if mistake.mistake_type not in by_type:
            by_type[mistake.mistake_type] = []
        by_type[mistake.mistake_type].append(mistake)
   
   # Calculate total cost
    total_cost = sum(m.cost_estimate or 0 for m in mistakes)
    
    # Most common mistake type
    if by_type:
        most_common_type = max(by_type, key=lambda k: len(by_type[k]))
        most_common_count = len(by_type[most_common_type])
    else:
        most_common_type = None
        most_common_count = 0
    
    return render_template('mistake_log.html',
                            title="Mistake Log",
                            mistakes=mistakes,
                            by_type=by_type,
                            total_cost=total_cost,
                            most_common_type=most_common_type,
                            most_common_count=most_common_count)

@learning_bp.route('/mistakes/new', methods=['GET', 'POST'])
@login_required
def new_mistake():
   """Log a new mistake"""
   if request.method == 'POST':
       title = request.form.get('title')
       description = request.form.get('description')
       mistake_type = request.form.get('mistake_type')
       severity = request.form.get('severity', type=int)
       cost_estimate = request.form.get('cost_estimate', type=float)
       company_id = request.form.get('company_id', type=int)
       root_cause = request.form.get('root_cause')
       lesson_learned = request.form.get('lesson_learned')
       
       if not title or not description or not lesson_learned:
           flash('Title, description, and lesson are required', 'error')
           return redirect(url_for('learning.new_mistake'))
       
       # Parse contributing factors and prevention steps
       contributing_factors = request.form.get('contributing_factors', '').split('\n')
       contributing_factors = [f.strip() for f in contributing_factors if f.strip()]
       
       prevention_steps = request.form.get('prevention_steps', '').split('\n')
       prevention_steps = [s.strip() for s in prevention_steps if s.strip()]
       
       mistake = MistakeLog(
           user=current_user,
           title=title,
           description=description,
           mistake_type=mistake_type,
           severity=severity or 5,
           cost_estimate=cost_estimate,
           company_id=company_id if company_id else None,
           root_cause=root_cause,
           contributing_factors=contributing_factors,
           lesson_learned=lesson_learned,
           prevention_steps=prevention_steps,
           process_changes=request.form.get('process_changes'),
           occurred_date=datetime.strptime(request.form.get('occurred_date'), '%Y-%m-%d').date() if request.form.get('occurred_date') else None
       )
       
       db.session.add(mistake)
       
       # Create a learning note from this mistake
       learning_note = LearningNote(
           author=current_user,
           title=f"Mistake: {title}",
           lesson=lesson_learned,
           category='mistake',
           context=description,
           how_to_apply='; '.join(prevention_steps) if prevention_steps else None,
           company_id=company_id if company_id else None,
           source_type='experience',
           importance=severity or 5,
           next_review_date=date.today() + timedelta(days=3)
       )
       db.session.add(learning_note)
       
       try:
           db.session.commit()
           flash('Mistake logged successfully! Remember to review it regularly.', 'success')
           return redirect(url_for('learning.mistake_log'))
       except Exception as e:
           db.session.rollback()
           flash(f'Error logging mistake: {str(e)}', 'error')
   
   companies = current_user.companies.order_by(Company.name).all()
   
   return render_template('new_mistake.html',
                         title="Log New Mistake",
                         companies=companies)

@learning_bp.route('/mistakes/<int:mistake_id>/review', methods=['POST'])
@login_required
def review_mistake(mistake_id):
   """Mark a mistake as reviewed"""
   mistake = MistakeLog.query.get_or_404(mistake_id)
   
   if mistake.user_id != current_user.id:
       return jsonify({'error': 'Access denied'}), 403
   
   mistake.times_reviewed += 1
   mistake.last_reviewed = now_utc()
   
   # Check if similar mistake was prevented
   prevented = request.json.get('prevented_similar', False)
   if prevented:
       mistake.prevented_similar += 1
   
   try:
       db.session.commit()
       return jsonify({
           'success': True,
           'times_reviewed': mistake.times_reviewed,
           'prevented_similar': mistake.prevented_similar
       })
   except Exception as e:
       db.session.rollback()
       return jsonify({'error': str(e)}), 500

@learning_bp.route('/weekly-review')
@login_required
def weekly_review():
   """Weekly review interface"""
   # Get current week dates
   today = date.today()
   week_start = today - timedelta(days=today.weekday())
   week_end = week_start + timedelta(days=6)
   
   # Check if review exists for this week
   existing_review = WeeklyReview.query.filter_by(
       user_id=current_user.id,
       week_start=week_start
   ).first()
   
   if existing_review:
       return redirect(url_for('learning.view_weekly_review', review_id=existing_review.id))
   
   # Get metrics for the week
   metrics = get_weekly_metrics(current_user.id, week_start)
   
   # Get past reviews for reference
   past_reviews = current_user.weekly_reviews.order_by(
       WeeklyReview.week_start.desc()
   ).limit(4).all()
   
   return render_template('weekly_review.html',
                         title="Weekly Review",
                         week_start=week_start,
                         week_end=week_end,
                         metrics=metrics,
                         past_reviews=past_reviews)

@learning_bp.route('/weekly-review/save', methods=['POST'])
@login_required
def save_weekly_review():
   """Save weekly review"""
   week_start = datetime.strptime(request.form.get('week_start'), '%Y-%m-%d').date()
   week_end = week_start + timedelta(days=6)
   
   # Check for existing review
   existing = WeeklyReview.query.filter_by(
       user_id=current_user.id,
       week_start=week_start
   ).first()
   
   if existing:
       review = existing
   else:
       review = WeeklyReview(
           user=current_user,
           week_start=week_start,
           week_end=week_end
       )
   
   # Get metrics
   metrics = get_weekly_metrics(current_user.id, week_start)
   review.ideas_captured = metrics['ideas_captured']
   review.ideas_killed = metrics['ideas_killed']
   review.research_hours = metrics['research_hours']
   review.decisions_made = metrics['decisions_made']
   
   # Save reflections
   review.biggest_win = request.form.get('biggest_win')
   review.biggest_challenge = request.form.get('biggest_challenge')
   review.market_thoughts = request.form.get('market_thoughts')
   review.confidence_level = request.form.get('confidence_level', type=int)
   review.market_sentiment = request.form.get('market_sentiment')
   
   # Parse lists
   key_learnings = request.form.get('key_learnings', '').split('\n')
   review.key_learnings = [l.strip() for l in key_learnings if l.strip()]
   
   opportunities = request.form.get('opportunities_identified', '').split('\n')
   review.opportunities_identified = [o.strip() for o in opportunities if o.strip()]
   
   risks = request.form.get('risks_identified', '').split('\n')
   review.risks_identified = [r.strip() for r in risks if r.strip()]
   
   priorities = request.form.get('next_week_priorities', '').split('\n')
   review.next_week_priorities = [p.strip() for p in priorities if p.strip()]

   review.completed_at = now_utc()

   if not existing:
       db.session.add(review)
   
   try:
       db.session.commit()
       flash('Weekly review saved successfully!', 'success')
       return redirect(url_for('learning.view_weekly_review', review_id=review.id))
   except Exception as e:
       db.session.rollback()
       flash(f'Error saving review: {str(e)}', 'error')
       return redirect(url_for('learning.weekly_review'))

@learning_bp.route('/weekly-review/<int:review_id>')
@login_required
def view_weekly_review(review_id):
   """View a specific weekly review"""
   review = WeeklyReview.query.get_or_404(review_id)
   
   if review.user_id != current_user.id:
       flash('Access denied', 'error')
       return redirect(url_for('learning.learning_dashboard'))
   
   return render_template('view_weekly_review.html',
                         title=f"Weekly Review: {review.week_start.strftime('%B %d, %Y')}",
                         review=review)

@learning_bp.route('/postmortem/<int:decision_id>', methods=['GET', 'POST'])
@login_required
def investment_postmortem(decision_id):
   """Create or view investment postmortem"""
   decision = DecisionJournal.query.get_or_404(decision_id)
   
   if decision.user_id != current_user.id:
       flash('Access denied', 'error')
       return redirect(url_for('learning.learning_dashboard'))
   
   # Check for existing postmortem
   existing = InvestmentPostMortem.query.filter_by(
       user_id=current_user.id,
       decision_id=decision_id
   ).first()
   
   if existing:
       return render_template('view_postmortem.html',
                             title="Investment Postmortem",
                             postmortem=existing,
                             decision=decision)
   
   if request.method == 'POST':
       postmortem = InvestmentPostMortem(
           user=current_user,
           company_id=decision.company_id,
           decision_id=decision_id,
           entry_date=datetime.strptime(request.form.get('entry_date'), '%Y-%m-%d').date(),
           exit_date=datetime.strptime(request.form.get('exit_date'), '%Y-%m-%d').date(),
           entry_price=request.form.get('entry_price', type=float),
           exit_price=request.form.get('exit_price', type=float),
           total_return=request.form.get('total_return', type=float),
           benchmark_return=request.form.get('benchmark_return', type=float),
           outcome=request.form.get('outcome'),
           thesis_accuracy=request.form.get('thesis_accuracy'),
           thesis_playing_out=request.form.get('thesis_playing_out'),
           decision_quality_score=request.form.get('decision_quality_score', type=int),
           process_followed=request.form.get('process_followed') == 'true',
           emotional_factors=request.form.get('emotional_factors'),
           primary_lesson=request.form.get('primary_lesson'),
           would_repeat=request.form.get('would_repeat') == 'true'
       )
       
       # Calculate holding period
       postmortem.holding_period_days = (postmortem.exit_date - postmortem.entry_date).days
       
       # Calculate annualized return
       if postmortem.holding_period_days > 0 and postmortem.total_return:
           years = postmortem.holding_period_days / 365
           postmortem.annualized_return = ((1 + postmortem.total_return / 100) ** (1 / years) - 1) * 100
       
       # Calculate alpha
       if postmortem.benchmark_return:
           postmortem.alpha = postmortem.total_return - postmortem.benchmark_return
       
       # Parse lists
       what_went_well = request.form.get('what_went_well', '').split('\n')
       postmortem.what_went_well = [w.strip() for w in what_went_well if w.strip()]
       
       what_went_poorly = request.form.get('what_went_poorly', '').split('\n')
       postmortem.what_went_poorly = [w.strip() for w in what_went_poorly if w.strip()]
       
       unexpected = request.form.get('unexpected_developments', '').split('\n')
       postmortem.unexpected_developments = [u.strip() for u in unexpected if u.strip()]
       
       lucky_breaks = request.form.get('lucky_breaks', '').split('\n')
       postmortem.lucky_breaks = [l.strip() for l in lucky_breaks if l.strip()]
       
       process_improvements = request.form.get('process_improvements', '').split('\n')
       postmortem.process_improvements = [p.strip() for p in process_improvements if p.strip()]
       
       db.session.add(postmortem)
       
       # Create learning note from postmortem
       learning_note = LearningNote(
           author=current_user,
           title=f"Postmortem: {decision.company.name if decision.company else 'Investment'}",
           lesson=postmortem.primary_lesson,
           category='postmortem',
           context=postmortem.thesis_playing_out,
           how_to_apply='; '.join(postmortem.process_improvements) if postmortem.process_improvements else None,
           company_id=decision.company_id,
           source_type='experience',
           importance=8 if postmortem.outcome == 'failure' else 6,
           next_review_date=date.today() + timedelta(days=7)
       )
       db.session.add(learning_note)
       
       try:
           db.session.commit()
           flash('Postmortem completed! The lessons have been added to your learning notes.', 'success')
           return redirect(url_for('learning.view_postmortem', postmortem_id=postmortem.id))
       except Exception as e:
           db.session.rollback()
           flash(f'Error saving postmortem: {str(e)}', 'error')
   
   return render_template('investment_postmortem.html',
                         title="Create Postmortem",
                         decision=decision)

@learning_bp.route('/postmortem/<int:postmortem_id>/view')
@login_required
def view_postmortem(postmortem_id):
   """View a completed postmortem"""
   postmortem = InvestmentPostMortem.query.get_or_404(postmortem_id)
   
   if postmortem.user_id != current_user.id:
       flash('Access denied', 'error')
       return redirect(url_for('learning.learning_dashboard'))
   
   return render_template('view_postmortem.html',
                         title="Investment Postmortem",
                         postmortem=postmortem)

@learning_bp.route('/patterns')
@login_required
def pattern_recognition():
   """View and manage recognized patterns"""
   # Get existing patterns
   patterns = current_user.patterns.order_by(
       PatternRecognition.impact_score.desc()
   ).all()
   
   # Run pattern identification
   new_patterns = identify_patterns(current_user.id)
   
   # Check if patterns already exist
   for pattern_data in new_patterns:
       existing = PatternRecognition.query.filter_by(
           user_id=current_user.id,
           pattern_name=pattern_data['name']
       ).first()
       
       if not existing:
           pattern = PatternRecognition(
               user=current_user,
               pattern_name=pattern_data['name'],
               pattern_type=pattern_data['type'],
               description=pattern_data['description'],
               occurrences=pattern_data['occurrences'],
               confidence_level=5,
               identified_date=date.today()
           )
           db.session.add(pattern)
           patterns.append(pattern)
       else:
           # Update occurrences
           existing.occurrences = pattern_data['occurrences']
           existing.last_observed = date.today()
   
   try:
       db.session.commit()
   except:
       db.session.rollback()
   
   # Categorize patterns
   success_patterns = [p for p in patterns if p.pattern_type == 'success_pattern']
   failure_patterns = [p for p in patterns if p.pattern_type == 'failure_pattern']
   behavioral_patterns = [p for p in patterns if p.pattern_type == 'behavioral']
   
   return render_template('pattern_recognition.html',
                         title="Pattern Recognition",
                         patterns=patterns,
                         success_patterns=success_patterns,
                         failure_patterns=failure_patterns,
                         behavioral_patterns=behavioral_patterns)

@learning_bp.route('/patterns/<int:pattern_id>/update', methods=['POST'])
@login_required
def update_pattern(pattern_id):
   """Update pattern details"""
   pattern = PatternRecognition.query.get_or_404(pattern_id)
   
   if pattern.user_id != current_user.id:
       return jsonify({'error': 'Access denied'}), 403
   
   data = request.json
   pattern.impact_score = data.get('impact_score', pattern.impact_score)
   pattern.confidence_level = data.get('confidence_level', pattern.confidence_level)
   pattern.how_to_leverage = data.get('how_to_leverage', pattern.how_to_leverage)
   pattern.how_to_avoid = data.get('how_to_avoid', pattern.how_to_avoid)
   pattern.financial_impact = data.get('financial_impact', pattern.financial_impact)
   
   try:
       db.session.commit()
       return jsonify({'success': True})
   except Exception as e:
       db.session.rollback()
       return jsonify({'error': str(e)}), 500

@learning_bp.route('/learning-paths')
@login_required
def learning_paths():
   """View and manage learning paths"""
   paths = current_user.learning_paths.order_by(
       LearningPath.status.desc(),
       LearningPath.created_at.desc()
   ).all()
   
   # Suggested paths based on weaknesses
   suggested_paths = []
   
   # Check for valuation weakness
   valuation_mistakes = MistakeLog.query.filter_by(
       user_id=current_user.id,
       mistake_type='analysis_error'
   ).count()
   
   if valuation_mistakes > 2:
       suggested_paths.append({
           'name': 'Valuation Mastery',
           'description': 'Improve your valuation skills',
           'skill_area': 'valuation'
       })
   
   return render_template('learning_paths.html',
                         title="Learning Paths",
                         paths=paths,
                         suggested_paths=suggested_paths)

@learning_bp.route('/learning-paths/create', methods=['POST'])
@login_required
def create_learning_path():
   """Create a new learning path"""
   name = request.form.get('name')
   description = request.form.get('description')
   skill_area = request.form.get('skill_area')
   target_completion = request.form.get('target_completion')
   milestones = request.form.getlist('milestones[]')
   
   if not name:
       flash('Path name is required', 'error')
       return redirect(url_for('learning.learning_paths'))
   
   # Filter out empty milestones
   milestones = [m.strip() for m in milestones if m.strip()]
   
   learning_path = LearningPath(
       user=current_user,
       name=name,
       description=description,
       skill_area=skill_area,
       status='active',
       total_steps=len(milestones),
       current_step=1,
       milestones=milestones,
       started_at=now_utc()
   )
   
   if target_completion:
       learning_path.target_completion = datetime.strptime(target_completion, '%Y-%m-%d').date()
   
   db.session.add(learning_path)
   
   try:
       db.session.commit()
       flash('Learning path created successfully!', 'success')
   except Exception as e:
       db.session.rollback()
       flash(f'Error creating learning path: {str(e)}', 'error')
   
   return redirect(url_for('learning.learning_paths'))

@learning_bp.route('/review-calendar')
@login_required
def review_calendar():
   """Show review calendar and schedule"""
   schedule = get_review_schedule(current_user.id)
   
   # Get past reviews
   past_reviews = {
       'weekly': current_user.weekly_reviews.order_by(WeeklyReview.week_start.desc()).limit(12).all(),
       'postmortems': current_user.postmortems.order_by(InvestmentPostMortem.created_at.desc()).limit(10).all(),
       'mistakes': current_user.mistake_logs.order_by(MistakeLog.last_reviewed.desc()).limit(10).all()
   }
   
   return render_template('review_calendar.html',
                         title="Review Calendar",
                         schedule=schedule,
                         past_reviews=past_reviews)