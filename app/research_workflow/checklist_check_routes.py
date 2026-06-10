# Investment Checklist Platform
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

import json
import os
import fitz
from datetime import datetime
from flask import jsonify, render_template, request, redirect, url_for, flash, current_app, Response
from flask_login import current_user, login_required
from flask import session as flask_session

from app import db
from app.models import Checklist, ChecklistItem, Company, ChecklistAnalysis, ChecklistAnswer, CompanyResource, QualitativeAnalysis
from app.research_workflow import research_workflow_bp
from app.utils.time_utils import now_utc
from app.utils.response_utils import json_error, json_unauthorized

# Import unified LLM service
from app.services.ai import ai_service
from app.services.ai.prompt_service import prompt_service
from app.services.background_tasks import BackgroundTaskService
from celery_app import celery
from app.utils.checklist_utils import get_all_ordered_items_for_checklist
from app.utils.blocknote_utils import blocknote_to_html
                                                                             
@research_workflow_bp.route('/for_company/<int:company_id>/select_checklist', methods=['GET'])
@login_required
def select_checklist_for_company(company_id):
    company = Company.query.get_or_404(company_id)
    if company.user_id != current_user.id:
    # Or if company.creator != current_user: (if using the backref)
        flash('You are not authorized to access this company.', 'error')
        return redirect(url_for('companies.list_companies'))

    user_checklists = Checklist.query.filter_by(user_id=current_user.id).order_by(Checklist.name).all()
    
    if not user_checklists:
        flash("You don't have any checklists yet. Please create one first.", 'warning')
        # Pass 'next' to redirect back here after creating a checklist
        return redirect(url_for('checklists.new_checklist', next=url_for('research_workflow.select_checklist_for_company', company_id=company_id)))

    checklists_data = []
    for chk in user_checklists:
        existing_session = ChecklistAnalysis.query.filter_by(
            user_id=current_user.id,
            company_id=company.id,
            checklist_id=chk.id
        ).first()
        
        session_info = {
            'checklist_obj': chk, # Store the actual checklist object
            'existing_session_id': None,
            'existing_session_status': None,
            'resume_item_id': None,
            'item_count': chk.items.count() # Get item count for display
        }

        if existing_session:
            session_info['existing_session_id'] = existing_session.id
            session_info['existing_session_status'] = existing_session.status
            if existing_session.status == 'in_progress':
                # Calculate resume_item_id for in-progress sessions
                all_items = get_all_ordered_items_for_checklist(chk.id)
                if all_items:
                    resume_id_candidate = all_items[0].id # Default to first item
                    for item in all_items:
                        ans_exists = ChecklistAnswer.query.filter_by(
                            checklist_analysis_id=existing_session.id, 
                            checklist_item_id=item.id
                        ).first()
                        if not ans_exists:
                            resume_id_candidate = item.id
                            break
                    session_info['resume_item_id'] = resume_id_candidate
                # If no items in checklist, resume_item_id remains None
        
        checklists_data.append(session_info)

    return render_template('select_checklist_for_company.html',
                           company=company,
                           checklists_data=checklists_data,
                           title=f"Select or Resume Research for {company.name}")
    
# This is the checklist execution route
@research_workflow_bp.route('/checklist/<int:analysis_id>/item/<int:item_id>', methods=['GET', 'POST'])
@login_required
def research_step(analysis_id, item_id):
    session = ChecklistAnalysis.query.get_or_404(analysis_id)
    current_item = ChecklistItem.query.get_or_404(item_id)
    if session.researcher != current_user: # Authorization check (assuming 'researcher' backref)
        flash('You are not authorized to access this research session.', 'error')
        return redirect(url_for('research_workflow.my_projects'))

    # Basic security check: ensure the item belongs to the session's checklist
    if current_item.checklist_id != session.checklist_id:
        flash('Invalid item for this research session.', 'error')
        return redirect(url_for('checklists.list_checklists')) # Or a more appropriate error page

    # Get the full ordered list of items for this session's checklist
    all_items_in_order = get_all_ordered_items_for_checklist(session.checklist_id)
    if not all_items_in_order:
        flash('Checklist has no items.', 'error')
        return redirect(url_for('checklists.view_checklist', checklist_id=session.checklist_id))

    current_item_index = -1
    for index, item_obj in enumerate(all_items_in_order):
        if item_obj.id == current_item.id:
            current_item_index = index
            break
    
    if current_item_index == -1: # Should not happen if item_id is valid and from this checklist
        flash('Error finding current item in checklist order.', 'error')
        return redirect(url_for('checklists.view_checklist', checklist_id=session.checklist_id))

    # Always fetch company resources (files) for the sidebar and AI analysis
    company_documents_for_llm = CompanyResource.query.filter_by(
        company_id=session.company_id, resource_type='file'
    ).order_by(CompanyResource.category, CompanyResource.resource_date.desc()).all()
        
    # Fetch existing answer for this item in this session
    research_answer = ChecklistAnswer.query.filter_by(
        checklist_analysis_id=session.id,
        checklist_item_id=current_item.id
    ).first()

    if request.method == 'POST':
        answer_text = request.form.get('answer_text')
        satisfaction_status_from_form = request.form.get('satisfaction_status') or 'neutral'
        if research_answer:
            research_answer.answer_text = answer_text
            research_answer.answered_at = now_utc()
            research_answer.satisfaction_status = satisfaction_status_from_form
        else:
            research_answer = ChecklistAnswer(
                answer_text=answer_text,
                checklist_analysis_id=session.id,
                checklist_item_id=current_item.id,
                satisfaction_status=satisfaction_status_from_form
            )
            db.session.add(research_answer)
        db.session.commit()
        flash('Answer saved.', 'success')

        # Determine next item
        if current_item_index + 1 < len(all_items_in_order):
            next_item = all_items_in_order[current_item_index + 1]
            return redirect(url_for('research_workflow.research_step', analysis_id=session.id, item_id=next_item.id))
        else:
            # This is the last item
            session.status = 'completed' # Mark session as completed
            db.session.commit()
            flash('Checklist completed! Research session finished.', 'success')
            # Redirect to a summary page or back to the checklist view for now
            return redirect(url_for('research_workflow.view_checklist_session_summary', analysis_id=session.id)) # We'll create this route next

    # For GET request or if POST needs to re-render
    # progress_percent = ( (current_item_index +1) / len(all_items_in_order) ) * 100 if all_items_in_order else 0
    progress_percent = (current_item_index) / len(all_items_in_order) * 100 if all_items_in_order else 0
    
    previous_item_id = None
    if current_item_index > 0 and all_items_in_order: # Check if not the first item
        previous_item_id = all_items_in_order[current_item_index - 1].id

    # Check for research workflow context
    research_context = flask_session.get('research_context')

    # Build answers map for checklist sidebar (status dots for all items)
    all_answers = ChecklistAnswer.query.filter_by(checklist_analysis_id=session.id).all()
    answers_map = {ans.checklist_item_id: ans for ans in all_answers}

    return render_template(
        'research_step.html',
        title=f"Research: {session.company.ticker_symbol} - Item {current_item_index + 1}/{len(all_items_in_order)}",
        session=session,
        current_item=current_item,
        answer=research_answer,
        current_item_number=current_item_index + 1,
        total_items=len(all_items_in_order),
        progress_percent=progress_percent,
        previous_item_id=previous_item_id,
        company_documents=company_documents_for_llm,
        research_context=research_context,
        all_items_in_order=all_items_in_order,
        answers_map=answers_map
    )

@research_workflow_bp.route('/checklist/<int:analysis_id>/item/<int:item_id>/json', methods=['GET'])
@login_required
def research_step_json(analysis_id, item_id):
    """
    AJAX endpoint: returns item data as JSON for smooth sidebar navigation.
    """
    session = ChecklistAnalysis.query.get_or_404(analysis_id)
    if session.researcher != current_user:
        return json_unauthorized('Unauthorized')

    current_item = ChecklistItem.query.get_or_404(item_id)
    if current_item.checklist_id != session.checklist_id:
        return json_error('Invalid item')

    all_items_in_order = get_all_ordered_items_for_checklist(session.checklist_id)

    current_item_index = -1
    for index, item_obj in enumerate(all_items_in_order):
        if item_obj.id == current_item.id:
            current_item_index = index
            break

    if current_item_index == -1:
        return jsonify({'error': 'Item not found in order'}), 400

    # Fetch answer
    research_answer = ChecklistAnswer.query.filter_by(
        checklist_analysis_id=session.id,
        checklist_item_id=current_item.id
    ).first()

    # Previous item
    previous_item_id = None
    if current_item_index > 0:
        previous_item_id = all_items_in_order[current_item_index - 1].id

    # Next item
    next_item_id = None
    is_last_item = False
    if current_item_index + 1 < len(all_items_in_order):
        next_item_id = all_items_in_order[current_item_index + 1].id
    else:
        is_last_item = True

    # All answers for sidebar status update
    all_answers = ChecklistAnswer.query.filter_by(checklist_analysis_id=session.id).all()
    answers_map = {}
    for ans in all_answers:
        answers_map[ans.checklist_item_id] = ans.satisfaction_status or 'neutral'

    # Status counts
    status_counts = {'satisfied': 0, 'not_satisfied': 0, 'needs_attention': 0, 'neutral': 0, 'pending': 0}
    for item in all_items_in_order:
        st = answers_map.get(item.id)
        if st and st in status_counts:
            status_counts[st] += 1
        else:
            status_counts['pending'] += 1

    return jsonify({
        'item_id': current_item.id,
        'item_number': current_item_index + 1,
        'total_items': len(all_items_in_order),
        'text': current_item.text,
        'description': current_item.description,
        'parent_text': current_item.parent.text if current_item.parent else None,
        'has_llm_prompt': bool(current_item.llm_prompt),
        'answer_text': research_answer.answer_text if research_answer else '',
        'satisfaction_status': research_answer.satisfaction_status if research_answer else 'pending',
        'previous_item_id': previous_item_id,
        'next_item_id': next_item_id,
        'is_last_item': is_last_item,
        'summary_url': url_for('research_workflow.view_checklist_session_summary', analysis_id=session.id),
        'autosave_url': url_for('research_workflow.autosave_research_answer', analysis_id=session.id, item_id=current_item.id),
        'form_action_url': url_for('research_workflow.research_step', analysis_id=session.id, item_id=current_item.id),
        'answers_map': answers_map,
        'status_counts': status_counts
    })


@research_workflow_bp.route('/checklist/<int:analysis_id>/item/<int:item_id>/autosave', methods=['POST'])
@login_required
def autosave_research_answer(analysis_id, item_id):
    """
    Auto-save endpoint for research answers - returns JSON for AJAX requests
    """
    try:
        session = ChecklistAnalysis.query.get_or_404(analysis_id)
        current_item = ChecklistItem.query.get_or_404(item_id)

        # Authorization check
        if session.researcher != current_user:
            return json_unauthorized('Unauthorized')

        # Security check: ensure the item belongs to the session's checklist
        if current_item.checklist_id != session.checklist_id:
            return json_error('Invalid item for this session')

        # Get data from request (supports both JSON and form data)
        if request.is_json:
            data = request.get_json()
            answer_text = data.get('content', '')
            satisfaction_status = data.get('satisfaction_status', 'neutral')
        else:
            answer_text = request.form.get('answer_text', '')
            satisfaction_status = request.form.get('satisfaction_status', 'neutral')

        # Find or create research answer
        research_answer = ChecklistAnswer.query.filter_by(
            checklist_analysis_id=session.id,
            checklist_item_id=current_item.id
        ).first()

        if research_answer:
            research_answer.answer_text = answer_text
            research_answer.answered_at = now_utc()
            research_answer.satisfaction_status = satisfaction_status
        else:
            research_answer = ChecklistAnswer(
                answer_text=answer_text,
                checklist_analysis_id=session.id,
                checklist_item_id=current_item.id,
                satisfaction_status=satisfaction_status
            )
            db.session.add(research_answer)

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Answer saved',
            'timestamp': research_answer.answered_at.isoformat() if research_answer.answered_at else None
        })

    except Exception as e:
        db.session.rollback()
        return json_error(str(e), status_code=500)

@research_workflow_bp.route('/checklist/<int:analysis_id>/item/<int:item_id>/save_and_next', methods=['POST'])
@login_required
def save_and_next(analysis_id, item_id):
    """
    AJAX endpoint: saves the answer and returns the next item ID (or summary URL for last item).
    """
    try:
        session = ChecklistAnalysis.query.get_or_404(analysis_id)
        current_item = ChecklistItem.query.get_or_404(item_id)

        if session.researcher != current_user:
            return json_unauthorized('Unauthorized')
        if current_item.checklist_id != session.checklist_id:
            return json_error('Invalid item for this session')

        # Parse request body
        if request.is_json:
            data = request.get_json()
            answer_text = data.get('content', '')
            satisfaction_status = data.get('satisfaction_status', 'neutral')
        else:
            answer_text = request.form.get('answer_text', '')
            satisfaction_status = request.form.get('satisfaction_status', 'neutral')

        # Save answer
        research_answer = ChecklistAnswer.query.filter_by(
            checklist_analysis_id=session.id,
            checklist_item_id=current_item.id
        ).first()

        if research_answer:
            research_answer.answer_text = answer_text
            research_answer.answered_at = now_utc()
            research_answer.satisfaction_status = satisfaction_status
        else:
            research_answer = ChecklistAnswer(
                answer_text=answer_text,
                checklist_analysis_id=session.id,
                checklist_item_id=current_item.id,
                satisfaction_status=satisfaction_status
            )
            db.session.add(research_answer)
        db.session.commit()

        # Determine next item
        all_items_in_order = get_all_ordered_items_for_checklist(session.checklist_id)
        current_item_index = next(
            (i for i, item in enumerate(all_items_in_order) if item.id == current_item.id), -1
        )

        if current_item_index + 1 < len(all_items_in_order):
            next_item = all_items_in_order[current_item_index + 1]
            return jsonify({
                'success': True,
                'is_last_item': False,
                'next_item_id': next_item.id
            })
        else:
            # Last item — mark session complete
            session.status = 'completed'
            db.session.commit()
            return jsonify({
                'success': True,
                'is_last_item': True,
                'summary_url': url_for('research_workflow.view_checklist_session_summary', analysis_id=session.id)
            })

    except Exception as e:
        db.session.rollback()
        return json_error(str(e), status_code=500)

@research_workflow_bp.route('/checklist/<int:analysis_id>/item/<int:item_id>/ai_analyze', methods=['POST'])
@login_required
def ai_analyze_item(analysis_id, item_id):
    """
    Dispatches a background Celery task for AI analysis of a checklist item.
    Returns a task_id for the frontend to poll for results.
    """
    if not ai_service.is_available():
        return jsonify({'status': 'error_config', 'message': 'AI service is not configured on the server.'}), 500

    session = ChecklistAnalysis.query.get_or_404(analysis_id)
    if session.researcher != current_user:
        return jsonify({'status': 'error', 'message': 'Unauthorized access to session.'}), 403

    item = ChecklistItem.query.get_or_404(item_id)
    if item.checklist_id != session.checklist_id:
        return jsonify({'status': 'error', 'message': 'Invalid item for this session.'}), 400

    if not request.is_json:
        return jsonify({'status': 'error', 'message': 'Invalid request: Content-Type must be application/json'}), 400

    data = request.get_json()
    if not data:
        return jsonify({'status': 'error', 'message': 'Invalid request: No JSON payload found.'}), 400

    # Parse document IDs
    selected_document_ids_str = data.get('selected_document_ids', [])
    selected_document_ids = []
    for doc_id_str in selected_document_ids_str:
        try:
            selected_document_ids.append(int(doc_id_str))
        except ValueError:
            return jsonify({'status': 'error', 'message': f'Invalid document ID format: "{doc_id_str}".'}), 400

    # Dispatch background task
    task_id = BackgroundTaskService.start_checklist_item_analysis(
        user_id=current_user.id,
        analysis_id=analysis_id,
        item_id=item_id,
        selected_document_ids=selected_document_ids
    )

    return jsonify({'success': True, 'task_id': task_id})


@research_workflow_bp.route('/checklist/ai_analyze/status/<task_id>')
@login_required
def ai_analyze_status(task_id):
    """Poll status of a checklist item AI analysis background task."""
    task_status = BackgroundTaskService.get_task_status(task_id)

    if not task_status:
        return jsonify({'state': 'NOT_FOUND'}), 404

    response = {
        'current': 0,
        'total': 100,
    }

    if task_status['status'] == 'pending':
        response['state'] = 'PENDING'
        response['current'] = 10
    elif task_status['status'] == 'running':
        response['state'] = 'RUNNING'
        response['current'] = 50
    elif task_status['status'] == 'completed':
        response['state'] = 'COMPLETED'
        response['current'] = 100
        result = task_status.get('result', {})
        response['ai_suggestion'] = result.get('ai_suggestion', '')
        response['received_prompt'] = result.get('received_prompt', '')
        response['tokens_used'] = result.get('tokens_used', 0)
    elif task_status['status'] == 'failed':
        response['state'] = 'FAILED'
        response['error'] = task_status.get('error', 'Analysis failed')

    return jsonify(response)

@research_workflow_bp.route('/checklist/<int:analysis_id>/summary', methods=['GET', 'POST'])
@login_required
def view_checklist_session_summary(analysis_id):
    # Fetch the core session object and authorize the user
    session = ChecklistAnalysis.query.get_or_404(analysis_id)
    if session.researcher != current_user:
        flash('You are not authorized to view this summary.', 'error')
        return redirect(url_for('research_workflow.my_projects'))
    
    # Handle POST request for updating the session's conclusion
    if request.method == 'POST':
        session.conclusion = request.form.get('conclusion')
        try:
            db.session.commit()
            # Return JSON for fetch requests from React island
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'message': 'Conclusion saved successfully.'})
            flash('Session conclusion saved successfully.', 'success')
        except Exception as e:
            db.session.rollback()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': str(e)}), 500
            flash(f'Error saving conclusion: {str(e)}', 'error')
        return redirect(url_for('research_workflow.view_checklist_session_summary', analysis_id=session.id))

    # --- GET Request Logic ---
    # Prepare all data needed for rendering the template

    # 1. Get all checklist items in their correct hierarchical order
    all_ordered_items = get_all_ordered_items_for_checklist(session.checklist_id)
    
    # 2. Fetch all answers for this session just once
    answers_for_session = ChecklistAnswer.query.filter_by(checklist_analysis_id=session.id).all()
    
    # 3. Create a dictionary that maps an item's ID to its full answer object for easy lookup in the template
    answers_map = {ans.checklist_item_id: ans for ans in answers_for_session}
    
    # 4. Pre-calculate the display values for the intrinsic value form
    intrinsic_display_value = ''
    intrinsic_unit = 1 # Default multiplier is 1
    if session.company.intrinsic_value:
        val = session.company.intrinsic_value
        if val >= 1_000_000_000_000:
            intrinsic_unit = 1_000_000_000_000
            intrinsic_display_value = f"{val / intrinsic_unit:.2f}"
        elif val >= 1_000_000_000:
            intrinsic_unit = 1_000_000_000
            intrinsic_display_value = f"{val / intrinsic_unit:.2f}"
        elif val >= 1_000_000:
            intrinsic_unit = 1_000_000
            intrinsic_display_value = f"{val / intrinsic_unit:.2f}"
        else:
            intrinsic_display_value = str(val)
    
    # 5. Check for research workflow context
    research_context = flask_session.get('research_context')

    # 6. Serialize questions + answers as JSON for the React island
    questions_data = []
    for item in all_ordered_items:
        ans = answers_map.get(item.id)
        questions_data.append({
            'id': item.id,
            'text': item.text,
            'parent': item.parent.text if item.parent else None,
            'status': ans.satisfaction_status if ans else 'not_answered',
            'answerHtml': blocknote_to_html(ans.answer_text) if ans and ans.answer_text else None,
        })
    questions_json = json.dumps(questions_data)

    # 7. Render the template, passing all the prepared data
    return render_template(
        'session_summary.html',
        title=f"Checklist Summary: {session.company.name}",
        session=session,
        all_ordered_items=all_ordered_items,
        answers_map=answers_map,
        intrinsic_display_value=intrinsic_display_value,
        intrinsic_unit=intrinsic_unit,
        research_context=research_context,
        questions_json=questions_json,
    )

def blocknote_to_text(blocknote_json):
    """Convert BlockNote JSON format to plain text"""
    if not blocknote_json:
        return ""

    try:
        blocks = json.loads(blocknote_json) if isinstance(blocknote_json, str) else blocknote_json

        text_parts = []
        for block in blocks:
            if block.get('type') == 'paragraph':
                content = block.get('content', [])
                paragraph_text = ''.join(item.get('text', '') for item in content if item.get('type') == 'text')
                if paragraph_text.strip():
                    text_parts.append(paragraph_text)
            elif block.get('type') == 'heading':
                content = block.get('content', [])
                heading_text = ''.join(item.get('text', '') for item in content if item.get('type') == 'text')
                level = block.get('props', {}).get('level', 1)
                if heading_text.strip():
                    text_parts.append('#' * level + ' ' + heading_text)
            elif block.get('type') == 'bulletListItem':
                content = block.get('content', [])
                item_text = ''.join(item.get('text', '') for item in content if item.get('type') == 'text')
                if item_text.strip():
                    text_parts.append('- ' + item_text)
            elif block.get('type') == 'numberedListItem':
                content = block.get('content', [])
                item_text = ''.join(item.get('text', '') for item in content if item.get('type') == 'text')
                if item_text.strip():
                    text_parts.append('1. ' + item_text)

        return '\n\n'.join(text_parts)
    except:
        # If parsing fails, return the raw text
        return str(blocknote_json)


@research_workflow_bp.route('/checklist/<int:analysis_id>/export/txt')
@login_required
def export_session_to_txt(analysis_id):
    # 1. Fetch session and authorize user
    session = ChecklistAnalysis.query.get_or_404(analysis_id)
    if session.researcher != current_user:
        flash('You are not authorized to export this research session.', 'error')
        return redirect(url_for('research_workflow.my_projects'))

    # 2. Gather all necessary data
    all_ordered_items = get_all_ordered_items_for_checklist(session.checklist_id)
    answers_for_session = ChecklistAnswer.query.filter_by(checklist_analysis_id=session.id).all()
    answers_map = {ans.checklist_item_id: ans for ans in answers_for_session}

    # 3. Construct the text content as a list of strings
    export_content = []
    export_content.append(f"# Research Summary: {session.company.name} ({session.company.ticker_symbol})")
    export_content.append(f"==================================================")
    export_content.append(f"Checklist Used: {session.checklist.name}")
    export_content.append(f"Research Date: {session.start_date.strftime('%Y-%m-%d')}")
    export_content.append(f"Status: {session.status.capitalize()}")
    export_content.append("\n")

    if session.conclusion:
        export_content.append(f"## Overall Conclusion")
        export_content.append(f"--------------------------")
        conclusion_text = blocknote_to_text(session.conclusion)
        export_content.append(conclusion_text)
        export_content.append("\n")

    export_content.append(f"## Individual Checklist Answers")
    export_content.append(f"--------------------------------")

    # Helper to recursively get item depth for indentation
    item_map = {item.id: item for item in all_ordered_items}
    def get_depth(item_id, depth=0):
        item = item_map.get(item_id)
        if item and item.parent_id in item_map:
            return get_depth(item.parent_id, depth + 1)
        return depth

    for item in all_ordered_items:
        indent = "  " * get_depth(item.id)
        answer_obj = answers_map.get(item.id)

        export_content.append(f"\n{indent}- **{item.text}**")

        if answer_obj:
            status = answer_obj.satisfaction_status.replace('_', ' ').capitalize() if answer_obj.satisfaction_status else 'Not Set'
            # Convert BlockNote JSON to readable text
            answer_text = blocknote_to_text(answer_obj.answer_text) if answer_obj.answer_text else "No text provided."
            export_content.append(f"{indent}  - **Status:** {status}")
            export_content.append(f"{indent}  - **Answer:** {answer_text}")
        else:
            export_content.append(f"{indent}  - **Status:** Not Answered")

    # 4. Join the content and prepare the file for download
    final_text = "\n".join(export_content)

    safe_company_name = "".join(c if c.isalnum() else "_" for c in session.company.name)
    filename = f"Research_{safe_company_name}_{analysis_id}.md" # Save as Markdown for nice formatting

    return Response(
        final_text,
        mimetype="text/markdown",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )


@research_workflow_bp.route('/task_status/<task_id>')
@login_required
def task_status(task_id):
    """
    Checks the status of a Celery background task.
    """
    task = celery.AsyncResult(task_id)

    response_data = {
        'state': task.state
    }

    if task.state == 'PENDING':
        response_data['status_message'] = 'Task is pending...'
    elif task.state == 'SUCCESS':
        response_data['result'] = task.info
        response_data['status_message'] = 'Task completed successfully!'
    elif task.state == 'FAILURE':
        # This is the key fix. On failure, task.info is the raw exception.
        # The custom error message we set in the task is stored in the task's metadata.
        # We access it through the task's result backend.
        if hasattr(task, 'backend') and hasattr(task.backend, 'get_task_meta'):
            meta = task.backend.get_task_meta(task.id)
            # Use our custom message if it exists, otherwise fall back to the raw exception string.
            response_data['status_message'] = meta.get('exc_message', str(task.info))
        else:
            response_data['status_message'] = str(task.info) # Fallback for different backends
    else:
        # For other states like 'PROGRESS' or 'STARTED'
        response_data['status_message'] = 'Task is in progress...'

    return jsonify(response_data)

@research_workflow_bp.route('/for_company/<int:company_id>/select_model')
@login_required
def select_model(company_id):
    company = Company.query.get_or_404(company_id)
    if company.user_id != current_user.id:
        flash("You are not authorized to access this company.", "error")
        return redirect(url_for('companies.list_companies'))

    # NEW: Check if there is at least one completed research session for this company
    has_completed_research = ChecklistAnalysis.query.filter_by(
        user_id=current_user.id,
        company_id=company.id,
        status='completed'
    ).first() is not None

    # Check if a SWOT analysis exists for this company
    has_swot_analysis = QualitativeAnalysis.query.filter_by(
        user_id=current_user.id,
        company_id=company.id,
        model_type='SWOT'
    ).first() is not None
    
    return render_template('select_model.html',
                           company=company,
                           has_completed_research=has_completed_research,
                           has_swot_analysis=has_swot_analysis,
                           title=f"Select Analysis Model for {company.name}")