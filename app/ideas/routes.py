from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user, login_required
from app import db
from app.models import (IdeaPipeline, KillChecklist, KillCriterion, 
                       KillSession, KillAnswer, Company)
from app.ideas import ideas_bp
from datetime import datetime, timedelta

@ideas_bp.route('/inbox')
@login_required
def inbox():
    """Display the user's idea inbox - ideas waiting to be evaluated"""
    ideas = current_user.idea_pipeline.filter_by(status='inbox')\
                                      .order_by(IdeaPipeline.created_at.desc()).all()
    
    # Get user's default kill checklist for the quick action
    default_kill_checklist = KillChecklist.query.filter_by(
        user_id=current_user.id, 
        is_default=True
    ).first()
    
    return render_template('inbox.html', 
                          title="Idea Inbox",
                          ideas=ideas,
                          default_kill_checklist=default_kill_checklist,
                          current_time=datetime.utcnow()
                          )

@ideas_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_idea():
    """Quick capture for new ideas"""
    if request.method == 'POST':
        name = request.form.get('name')
        idea_type = request.form.get('idea_type', 'company')
        ticker = request.form.get('ticker_symbol', '').upper()
        source = request.form.get('source')
        thesis = request.form.get('thesis_summary')
        notes = request.form.get('initial_notes')
        
        if not name:
            flash('Idea name is required', 'error')
            return redirect(url_for('ideas.add_idea'))
        
        new_idea = IdeaPipeline(
            author=current_user,
            name=name,
            idea_type=idea_type,
            ticker_symbol=ticker if ticker else None,
            source=source,
            thesis_summary=thesis,
            initial_notes=notes,
            status='inbox'
        )
        
        try:
            db.session.add(new_idea)
            db.session.commit()
            flash(f'"{name}" added to your idea inbox!', 'success')
            
            # Ask if they want to evaluate it immediately
            return redirect(url_for('ideas.inbox'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding idea: {str(e)}', 'error')
    
    return render_template('add_idea.html', title="Quick Capture")

@ideas_bp.route('/<int:idea_id>/kill', methods=['GET', 'POST'])
@login_required
def kill_room(idea_id):
    """The kill room - evaluate an idea against kill criteria"""
    idea = IdeaPipeline.query.get_or_404(idea_id)
    
    # Security check
    if idea.user_id != current_user.id:
        flash('You do not have access to this idea', 'error')
        return redirect(url_for('ideas.inbox'))
    
    # Get or create kill session
    kill_session = KillSession.query.filter_by(
        user_id=current_user.id,
        idea_id=idea.id,
        outcome=None  # Unfinished session
    ).first()
    
    if not kill_session:
        # Start new kill session with default checklist
        kill_checklist = KillChecklist.query.filter_by(
            user_id=current_user.id,
            is_default=True
        ).first()
        
        if not kill_checklist:
            flash('Please create a kill checklist first', 'warning')
            return redirect(url_for('ideas.create_kill_checklist'))
        
        kill_session = KillSession(
            user_id=current_user.id,
            idea=idea,
            checklist=kill_checklist
        )
        db.session.add(kill_session)
        db.session.commit()
        
        # Update idea status
        idea.status = 'killing'
        db.session.commit()
    
    # Get all criteria for this checklist
    criteria = kill_session.checklist.criteria.order_by(KillCriterion.order).all()
    
    # Get existing answers
    existing_answers = {
        ans.criterion_id: ans 
        for ans in kill_session.answers.all()
    }
    
    # Find current criterion (first unanswered)
    current_criterion = None
    current_index = 0
    for i, criterion in enumerate(criteria):
        if criterion.id not in existing_answers:
            current_criterion = criterion
            current_index = i
            break
    
    if request.method == 'POST':
        if current_criterion:
            # Process answer
            passed = request.form.get('passed') == 'true'
            notes = request.form.get('notes', '')
            
            # Save answer
            answer = KillAnswer(
                session=kill_session,
                criterion=current_criterion,
                passed=passed,
                notes=notes
            )
            db.session.add(answer)
            
            # Update criterion statistics
            current_criterion.times_evaluated += 1
            if not passed:
                current_criterion.times_failed += 1
            
            if not passed:
                # Idea failed - kill it
                idea.status = 'killed'
                idea.kill_reason = current_criterion.question
                idea.failed_criterion = current_criterion
                idea.killed_at = datetime.utcnow()
                
                kill_session.outcome = 'killed'
                kill_session.completed_at = datetime.utcnow()
                
                # Update checklist stats
                kill_session.checklist.total_ideas_evaluated += 1
                kill_session.checklist.total_ideas_killed += 1
                
                db.session.commit()
                
                flash(f'"{idea.name}" has been killed. Reason: {current_criterion.question}', 'info')
                return redirect(url_for('ideas.graveyard'))
            
            db.session.commit()
            
            # Check if we've completed all criteria
            if current_index == len(criteria) - 1:
                # Survived all criteria!
                idea.status = 'promoted'
                idea.promoted_at = datetime.utcnow()
                
                kill_session.outcome = 'survived'
                kill_session.completed_at = datetime.utcnow()
                
                # Update checklist stats
                kill_session.checklist.total_ideas_evaluated += 1
                
                db.session.commit()
                
                flash(f'🎉 "{idea.name}" survived the kill checklist! Ready for deep research.', 'success')
                return redirect(url_for('ideas.promote_to_company', idea_id=idea.id))
            
            # Continue to next criterion
            return redirect(url_for('ideas.kill_room', idea_id=idea.id))
    
    # Calculate progress
    progress_percent = (len(existing_answers) / len(criteria)) * 100 if criteria else 0
    
    return render_template('kill_room.html',
                          title=f"Kill Room: {idea.name}",
                          idea=idea,
                          session=kill_session,
                          current_criterion=current_criterion,
                          current_index=current_index,
                          total_criteria=len(criteria),
                          progress_percent=progress_percent,
                          existing_answers=existing_answers)

@ideas_bp.route('/graveyard')
@login_required
def graveyard():
    """View killed ideas - learn from past eliminations"""
    killed_ideas = current_user.idea_pipeline.filter_by(status='killed')\
                                             .order_by(IdeaPipeline.killed_at.desc()).all()
    
    # Group by kill reason for analysis
    kill_reasons = {}
    for idea in killed_ideas:
        reason = idea.kill_reason or "Unknown"
        if reason not in kill_reasons:
            kill_reasons[reason] = []
        kill_reasons[reason].append(idea)
    
    return render_template('graveyard.html',
                          title="Idea Graveyard",
                          killed_ideas=killed_ideas,
                          kill_reasons=kill_reasons)

@ideas_bp.route('/kill-checklists')
@login_required
def manage_kill_checklists():
    """Manage kill checklists"""
    checklists = current_user.kill_checklists.all()
    
    return render_template('manage_kill_checklists.html',
                          title="Kill Checklists",
                          checklists=checklists)

@ideas_bp.route('/kill-checklists/new', methods=['GET', 'POST'])
@login_required
def create_kill_checklist():
    """Create a new kill checklist"""
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        is_default = request.form.get('is_default') == 'true'
        
        if not name:
            flash('Checklist name is required', 'error')
            return redirect(url_for('ideas.create_kill_checklist'))
        
        # If setting as default, unset other defaults
        if is_default:
            KillChecklist.query.filter_by(user_id=current_user.id, is_default=True)\
                              .update({'is_default': False})
        
        checklist = KillChecklist(
            author=current_user,
            name=name,
            description=description,
            is_default=is_default
        )
        db.session.add(checklist)
        db.session.flush()  # Get the ID
        
        # Add initial criteria from form
        criteria_questions = request.form.getlist('criterion_question[]')
        criteria_reasons = request.form.getlist('criterion_reason[]')
        
        for i, question in enumerate(criteria_questions):
            if question.strip():
                criterion = KillCriterion(
                    checklist=checklist,
                    question=question.strip(),
                    failure_reason=criteria_reasons[i] if i < len(criteria_reasons) else '',
                    order=i
                )
                db.session.add(criterion)
        
        db.session.commit()
        flash(f'Kill checklist "{name}" created!', 'success')
        return redirect(url_for('ideas.manage_kill_checklists'))
    
    return render_template('create_kill_checklist.html', 
                          title="Create Kill Checklist")

@ideas_bp.route('/<int:idea_id>/promote', methods=['GET', 'POST'])
@login_required
def promote_to_company(idea_id):
    """Promote a surviving idea to a full company for research"""
    idea = IdeaPipeline.query.get_or_404(idea_id)
    
    if idea.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('ideas.inbox'))
    
    if request.method == 'POST':
        # Create company from idea
        company = Company(
            name=idea.name,
            ticker_symbol=idea.ticker_symbol,
            creator=current_user,
            summary=idea.thesis_summary
        )
        db.session.add(company)
        db.session.flush()
        
        # Link idea to company
        idea.promoted_to_company = company
        idea.status = 'promoted'
        idea.promoted_at = datetime.utcnow()
        
        db.session.commit()
        
        flash(f'"{idea.name}" promoted to your companies list! You can now begin deep research.', 'success')
        return redirect(url_for('research.select_checklist_for_company', 
                               company_id=company.id))
    
    return render_template('promote_idea.html',
                          title="Promote to Company",
                          idea=idea)

@ideas_bp.route('/<int:idea_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_idea(idea_id):
    """Edit an idea in the inbox"""
    idea = IdeaPipeline.query.get_or_404(idea_id)
    
    if idea.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('ideas.inbox'))
    
    if request.method == 'POST':
        idea.name = request.form.get('name', idea.name)
        idea.idea_type = request.form.get('idea_type', idea.idea_type)
        idea.ticker_symbol = request.form.get('ticker_symbol', '').upper() or None
        idea.source = request.form.get('source')
        idea.thesis_summary = request.form.get('thesis_summary')
        idea.initial_notes = request.form.get('initial_notes')
        
        try:
            db.session.commit()
            flash('Idea updated successfully', 'success')
            return redirect(url_for('ideas.inbox'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating idea: {str(e)}', 'error')
    
    return render_template('edit_idea.html', 
                          title="Edit Idea", 
                          idea=idea)

@ideas_bp.route('/<int:idea_id>/delete', methods=['POST'])
@login_required
def delete_idea(idea_id):
    """Delete an idea permanently"""
    idea = IdeaPipeline.query.get_or_404(idea_id)
    
    if idea.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('ideas.inbox'))
    
    try:
        db.session.delete(idea)
        db.session.commit()
        flash(f'"{idea.name}" deleted permanently', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting idea: {str(e)}', 'error')
    
    return redirect(url_for('ideas.inbox'))

@ideas_bp.route('/<int:idea_id>/resurrect', methods=['POST'])
@login_required
def resurrect_idea(idea_id):
    """Resurrect a killed idea back to inbox"""
    idea = IdeaPipeline.query.get_or_404(idea_id)
    
    if idea.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    idea.status = 'inbox'
    idea.kill_reason = None
    idea.failed_criterion_id = None
    idea.killed_at = None
    
    try:
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@ideas_bp.route('/<int:idea_id>/mark_someday', methods=['GET'])
@login_required
def mark_someday(idea_id):
    """Move idea to someday/maybe status"""
    idea = IdeaPipeline.query.get_or_404(idea_id)
    
    if idea.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('ideas.inbox'))
    
    idea.status = 'someday'
    idea.last_reviewed_at = datetime.utcnow()
    
    try:
        db.session.commit()
        flash(f'"{idea.name}" moved to Someday/Maybe', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating idea: {str(e)}', 'error')
    
    return redirect(url_for('ideas.inbox'))

@ideas_bp.route('/kill-checklists/<int:checklist_id>/set-default', methods=['POST'])
@login_required
def set_default_checklist(checklist_id):
    """Set a kill checklist as default"""
    checklist = KillChecklist.query.get_or_404(checklist_id)
    
    if checklist.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('ideas.manage_kill_checklists'))
    
    # Unset other defaults
    KillChecklist.query.filter_by(user_id=current_user.id, is_default=True)\
                      .update({'is_default': False})
    
    checklist.is_default = True
    
    try:
        db.session.commit()
        flash(f'"{checklist.name}" set as default kill checklist', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating checklist: {str(e)}', 'error')
    
    return redirect(url_for('ideas.manage_kill_checklists'))    