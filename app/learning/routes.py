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
from app import db
from app.models import (MistakeLog, InvestmentPostMortem,
                       PatternRecognition, DecisionJournal,
                       Company, LearningNote)
from app.learning import learning_bp
from app.utils.time_utils import now_utc, parse_date_to_date_object
from datetime import datetime, timedelta, date

@learning_bp.route('/dashboard')
@login_required
def learning_dashboard():
    """Redirect to unified Knowledge Hub"""
    return redirect(url_for('journal_enhanced.knowledge_hub'))

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
           occurred_date=parse_date_to_date_object(request.form.get('occurred_date'))
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

@learning_bp.route('/postmortem/<int:decision_id>', methods=['GET', 'POST'])
@login_required
def investment_postmortem(decision_id):
   """Create or view investment postmortem"""
   decision = DecisionJournal.query.get_or_404(decision_id)
   
   if decision.user_id != current_user.id:
       flash('Access denied', 'error')
       return redirect(url_for('journal_enhanced.knowledge_hub'))
   
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
           entry_date=parse_date_to_date_object(request.form.get('entry_date')),
           exit_date=parse_date_to_date_object(request.form.get('exit_date')),
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
       return redirect(url_for('journal_enhanced.knowledge_hub'))
   
   return render_template('view_postmortem.html',
                         title="Investment Postmortem",
                         postmortem=postmortem)

@learning_bp.route('/postmortems')
@login_required
def postmortem_list():
    """List all completed investment postmortems"""
    postmortems = current_user.postmortems.order_by(
        InvestmentPostMortem.created_at.desc()
    ).all()

    return render_template('postmortem_list.html',
                          title="Investment Postmortems",
                          postmortems=postmortems)