from flask import jsonify, render_template, request, redirect, url_for, flash, current_app, Response
from flask_login import current_user, login_required
from flask import session as flask_session

from app import db
from app.models import Checklist, ChecklistItem, Company, ResearchSession, ResearchAnswer, CompanyDocument, QualitativeAnalysis
from app.research import research_bp # Import the new blueprint

# Utility imports needed for document handling
import os
from datetime import datetime
import fitz
from app.utils.time_utils import now_utc

# For LLM-related functionality, ensure you have the transformers library installed
from transformers import pipeline, AutoTokenizer, TFAutoModelForSeq2SeqLM # Or AutoModelForSeq2SeqLM for PyTorch

# Import unified LLM service
from app.services.llm_service import generate_ai_content

from celery.result import AsyncResult
from celery_app import celery

# Global variable for the LLM pipeline (loaded once)
llm_pipeline = None
LLM_MODEL_NAME = "google/flan-t5-small"

def get_all_ordered_items_for_checklist(checklist_id):
    """
    Returns a flat list of all checklist items for a given checklist_id,
    ordered by their sequence and hierarchy (depth-first).
    """
    return _get_ordered_checklist_items_recursive(None, checklist_id)

def _get_ordered_checklist_items_recursive(parent_item_id, checklist_id):
    """
    Recursive helper to fetch items and their children in order.
    """
    ordered_items = []
    if parent_item_id is None: # Top-level items
        items = ChecklistItem.query.filter_by(checklist_id=checklist_id, parent_id=None).order_by(ChecklistItem.order).all()
    else: # Sub-items
        items = ChecklistItem.query.filter_by(checklist_id=checklist_id, parent_id=parent_item_id).order_by(ChecklistItem.order).all()

    for item in items:
        ordered_items.append(item)
        ordered_items.extend(_get_ordered_checklist_items_recursive(item.id, checklist_id))
    return ordered_items

def initialize_llm_pipeline():
    global llm_pipeline
    if llm_pipeline is None:
        try:
            print(f"INFO: Initializing local LLM model: {LLM_MODEL_NAME}...")
            tokenizer = AutoTokenizer.from_pretrained(LLM_MODEL_NAME)
            llm_pipeline = pipeline("text2text-generation", model=LLM_MODEL_NAME, tokenizer=tokenizer)
            print(f"INFO: Local LLM pipeline ({LLM_MODEL_NAME}) initialized successfully.")
        except Exception as e:
            print(f"ERROR: Failed to initialize local LLM pipeline: {e}")
                                                                                                        
@research_bp.route('/for_company/<int:company_id>/select_checklist', methods=['GET'])
@login_required
def select_checklist_for_company(company_id):
    company = Company.query.get_or_404(company_id)
    if company.user_id != current_user.id:
    # Or if company.creator != current_user: (if using the backref)
        flash('You are not authorized to access this company.', 'error')
        return redirect(url_for('companies.companies_dashboard'))

    user_checklists = Checklist.query.filter_by(user_id=current_user.id).order_by(Checklist.name).all()
    
    if not user_checklists:
        flash("You don't have any checklists yet. Please create one first.", 'warning')
        # Pass 'next' to redirect back here after creating a checklist
        return redirect(url_for('checklists.new_checklist', next=url_for('research.select_checklist_for_company', company_id=company_id)))

    checklists_data = []
    for chk in user_checklists:
        existing_session = ResearchSession.query.filter_by(
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
                        ans_exists = ResearchAnswer.query.filter_by(
                            research_session_id=existing_session.id, 
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
@research_bp.route('/session/<int:session_id>/item/<int:item_id>', methods=['GET', 'POST'])
@login_required
def research_step(session_id, item_id):
    session = ResearchSession.query.get_or_404(session_id)
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

    # Always fetch company documents for the sidebar and AI analysis
    company_documents_for_llm = CompanyDocument.query.filter_by(company_id=session.company_id)\
                                            .order_by(CompanyDocument.document_group, CompanyDocument.document_date.desc())\
                                            .all()
        
    # Fetch existing answer for this item in this session
    research_answer = ResearchAnswer.query.filter_by(
        research_session_id=session.id,
        checklist_item_id=current_item.id
    ).first()

    if request.method == 'POST':
        answer_text = request.form.get('answer_text')
        satisfaction_status_from_form = request.form.get('satisfaction_status') # Get the new status
        if research_answer:
            research_answer.answer_text = answer_text
            research_answer.answered_at = now_utc()
            research_answer.satisfaction_status = satisfaction_status_from_form
        else:
            research_answer = ResearchAnswer(
                answer_text=answer_text,
                research_session_id=session.id,
                checklist_item_id=current_item.id,
                satisfaction_status=satisfaction_status_from_form
            )
            db.session.add(research_answer)
        db.session.commit()
        flash('Answer saved.', 'success')

        # Determine next item
        if current_item_index + 1 < len(all_items_in_order):
            next_item = all_items_in_order[current_item_index + 1]
            return redirect(url_for('research.research_step', session_id=session.id, item_id=next_item.id))
        else:
            # This is the last item
            session.status = 'completed' # Mark session as completed
            db.session.commit()
            flash('Checklist completed! Research session finished.', 'success')
            # Redirect to a summary page or back to the checklist view for now
            return redirect(url_for('research.view_checklist_session_summary', session_id=session.id)) # We'll create this route next

    # For GET request or if POST needs to re-render
    # progress_percent = ( (current_item_index +1) / len(all_items_in_order) ) * 100 if all_items_in_order else 0
    progress_percent = (current_item_index) / len(all_items_in_order) * 100 if all_items_in_order else 0
    
    previous_item_id = None
    if current_item_index > 0 and all_items_in_order: # Check if not the first item
        previous_item_id = all_items_in_order[current_item_index - 1].id

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
        company_documents=company_documents_for_llm 
    )
    
@research_bp.route('/session/<int:session_id>/item/<int:item_id>/ai_analyze', methods=['POST'])
@login_required
def ai_analyze_item(session_id, item_id):
    """
    Handles the AI analysis request for a specific checklist item within a research session.
    It extracts text from selected documents, calls the LLM, and returns a suggestion.
    """
    gemini_api_key = current_app.config.get('GEMINI_API_KEY')
    if not gemini_api_key:
        return jsonify({'status': 'error_config', 'message': 'Gemini API key is not configured on the server.'}), 500

    # LLM service will handle API configuration automatically
    session = ResearchSession.query.get_or_404(session_id)
    # Authorization: Ensure the session belongs to the current user
    if session.researcher != current_user:
        return jsonify({'status': 'error', 'message': 'Unauthorized access to session.'}), 403
    
    item = ChecklistItem.query.get_or_404(item_id)
    if item.checklist_id != session.checklist_id:
        return jsonify({'status': 'error', 'message': 'Invalid item for this session.'}), 400

    # Ensure the request is JSON
    if not request.is_json:
        return jsonify({'status': 'error', 'message': 'Invalid request: Content-Type must be application/json'}), 400
    
    data = request.get_json()
    if not data:
        return jsonify({'status': 'error', 'message': 'Invalid request: No JSON payload found.'}), 400
    
    selected_model = data.get('selected_model', 'local') # Default to 'local' if not specified
    llm_question = data.get('llm_actual_prompt', item.llm_prompt)


    selected_document_ids_str = data.get('selected_document_ids', [])
    
    # Convert document IDs from strings to integers
    selected_document_ids = []
    for doc_id_str in selected_document_ids_str:
        try:
            selected_document_ids.append(int(doc_id_str))
        except ValueError:
            return jsonify({'status': 'error', 'message': f'Invalid document ID format: "{doc_id_str}". IDs must be integers.'}), 400

    # Print received data for debugging (server-side)
    print(f"AI Analysis Request for Session {session_id}, Item {item_id}")
    print(f"LLM Question: {llm_question}")
    print(f"Selected Document IDs (integers): {selected_document_ids}")

    validated_documents_info = []
    aggregated_text_content = ""

    # Process selected documents if any IDs were provided
    if selected_document_ids:
        # Fetch CompanyDocument objects, ensuring they belong to the session's company
        company_documents = CompanyDocument.query.filter(
            CompanyDocument.id.in_(selected_document_ids),
            CompanyDocument.company_id == session.company_id 
        ).all()

        # Validate that all requested document IDs were found and valid for this company
        if len(company_documents) != len(set(selected_document_ids)):
            return jsonify({'status': 'error', 'message': 'Some selected documents are invalid or not found for this company.'}), 400
            
        for doc in company_documents:
            validated_documents_info.append({
                'id': doc.id, 'title': doc.document_title, 'filename': doc.original_filename
            })
            
            # Extract text content from each validated document
            try:
                full_file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], doc.stored_filename)
                if not os.path.exists(full_file_path):
                    error_msg = f"\n\n--- ERROR: File not found for document: {doc.original_filename} (Path: {full_file_path}) ---"
                    aggregated_text_content += error_msg
                    print(error_msg.strip()) # Log server-side
                    continue # Skip to the next document
                
                if doc.original_filename.lower().endswith('.pdf'):
                    with fitz.open(full_file_path) as pdf_doc:
                        for page in pdf_doc:
                            aggregated_text_content += page.get_text("text") + "\n"
                elif doc.original_filename.lower().endswith('.txt'):
                    with open(full_file_path, 'r', encoding='utf-8') as txt_file:
                        aggregated_text_content += txt_file.read() + "\n"
                else:
                    aggregated_text_content += f"\n\n--- Skipped unsupported file type: {doc.original_filename} ---"
            except Exception as e:
                error_msg = f"\n\n--- ERROR processing document {doc.original_filename}: {str(e)} ---"
                aggregated_text_content += error_msg
                print(f"ERROR: Failed to process file {doc.original_filename}: {e}") # Log server-side
    
    # Initialize response variables
    ai_suggestion = "Analysis could not be performed."
    response_status = 'pending'
    response_message = ''

    if selected_model == 'gemini':
        print("INFO: Using Gemini API for analysis.")
        gemini_api_key = current_app.config.get('GEMINI_API_KEY')

        if not gemini_api_key:
            response_status = 'error_config'
            response_message = 'Gemini API key is not configured on the server.'
            ai_suggestion = 'Gemini API key missing.'
        else:
            try:
                # Construct the prompt for the unified LLM service
                prompt_for_llm = (
                    "You are a helpful financial analyst assistant. Your task is to answer the user's question based strictly "
                    "on the context provided from the financial documents. Do not use external knowledge. "
                    "If the answer is not found in the context, state that clearly.\n\n"
                    f"CONTEXT:\n---\n{aggregated_text_content}\n---\n\n"
                    f"QUESTION:\n{llm_question}"
                )

                print("INFO: Sending prompt to unified LLM service...")
                # Generate content using unified LLM service
                ai_suggestion = generate_ai_content(prompt_for_llm)
                response_status = 'success_ai_suggestion'
                response_message = 'Suggestion generated successfully by Gemini API.'
                print("INFO: Gemini suggestion received.")

            except Exception as e:
                response_status = 'error_api_call'
                response_message = 'An error occurred while calling the Gemini API.'
                ai_suggestion = "The AI service returned an error. This could be due to content safety filters, API key issues, or other upstream errors. Please check the server logs."
                print(f"ERROR: Gemini API call error: {e}")
            
    elif selected_model == 'local':
            # --- EXECUTE LOCAL HUGGING FACE MODEL LOGIC ---
            print("INFO: Using local model for analysis.")
            
            # Ensure the local model pipeline is initialized (lazy loads on first use)
            initialize_llm_pipeline()
            
            if not llm_pipeline:
                # This block runs if the initialize_llm_pipeline function failed
                response_status = 'error_llm_not_loaded'
                response_message = "The local AI model could not be initialized. Please check server logs."
                ai_suggestion = "AI model unavailable."
            elif not aggregated_text_content.strip():
                # This block runs if documents were selected but no text could be extracted
                response_status = 'warning_no_text_extracted'
                response_message = "Could not extract usable text from the selected documents."
                ai_suggestion = "No text available from selected documents for the AI to analyze."
            else:
                # If the pipeline is loaded and we have text, proceed with analysis
                try:
                    # --- Prepare context and prompt specifically for the local model ---
                    tokenizer = llm_pipeline.tokenizer
                    
                    # Instruction-tune the prompt for better results
                    instructions = "Answer the following question based only on the provided context. If the answer is not in the context, state that the information is not found in the provided documents."
                    
                    # Calculate token counts to avoid exceeding the model's max input length (e.g., 512 for T5-small)
                    instruction_token_ids = tokenizer.encode(instructions, add_special_tokens=False)
                    question_token_ids = tokenizer.encode(llm_question, add_special_tokens=False)
                    template_overhead_tokens = 20 # Estimate for separators like "QUESTION:", "CONTEXT:", etc.
                    
                    # Calculate how many tokens are left for the actual document context
                    available_for_context_tokens = tokenizer.model_max_length - len(instruction_token_ids) - len(question_token_ids) - template_overhead_tokens
                    
                    if available_for_context_tokens < 50: # Ensure we have at least some space for context
                        print("WARNING: Long question/instructions leave little room for document context.")
                        available_for_context_tokens = 50

                    # Truncate the extracted document text to fit the available token space
                    context_input_ids = tokenizer.encode(
                        aggregated_text_content,
                        max_length=available_for_context_tokens,
                        truncation=True,
                        add_special_tokens=False 
                    )
                    truncated_context = tokenizer.decode(context_input_ids, skip_special_tokens=True)

                    # Construct the final prompt
                    prompt_for_llm = f"{instructions}\n\nQUESTION:\n{llm_question}\n\nCONTEXT:\n{truncated_context}\n\nANSWER:"
                    
                    print(f"INFO: Sending prompt to local LLM. Input tokens approx: {len(tokenizer.encode(prompt_for_llm))}")

                    # --- Call the local LLM pipeline ---
                    generated_outputs = llm_pipeline(prompt_for_llm, max_new_tokens=150, min_length=10)
                    
                    if generated_outputs and isinstance(generated_outputs, list) and generated_outputs[0].get('generated_text'):
                        ai_suggestion = generated_outputs[0]['generated_text'].strip()
                        if ai_suggestion:
                            response_status = 'success_ai_suggestion'
                            response_message = f'Suggestion generated by local model ({LLM_MODEL_NAME}).'
                        else:
                            response_status = 'warning_llm_empty_response'
                            response_message = 'Local model generated an empty suggestion.'
                            ai_suggestion = "The local AI did not provide a suggestion for this query."
                    else:
                        response_status = 'error_llm_unexpected_response'
                        response_message = 'Local model returned an unexpected response format.'
                        ai_suggestion = "Could not understand local AI's response."

                except Exception as e:
                    response_status = 'error_llm_inference'
                    response_message = 'An error occurred during local model inference.'
                    ai_suggestion = f"Local model error: {str(e)}"
                    print(f"ERROR: Local model inference error: {e}")
                              
    else:
        response_status = 'error_invalid_model'
        response_message = f"Invalid model '{selected_model}' selected."

    # --- Construct and return the JSON response ---
    return jsonify({
        'status': response_status,
        'message': response_message,
        'received_prompt': llm_question,
        'selected_documents_info': validated_documents_info, # Assuming this is populated
        'extracted_text_sample': aggregated_text_content[:500] + ("..." if len(aggregated_text_content) > 500 else ""),
        'ai_suggestion': ai_suggestion
    })
    
# We also need a route for the session summary. Let's add a placeholder for now.
@research_bp.route('/session/<int:session_id>/summary', methods=['GET', 'POST'])
@login_required
def view_checklist_session_summary(session_id):
    # Fetch the core session object and authorize the user
    session = ResearchSession.query.get_or_404(session_id)
    if session.researcher != current_user:
        flash('You are not authorized to view this summary.', 'error')
        return redirect(url_for('research_workflow.my_projects'))
    
    # Handle POST request for updating the session's conclusion
    if request.method == 'POST':
        session.conclusion = request.form.get('conclusion')
        try:
            db.session.commit()
            flash('Session conclusion saved successfully.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving conclusion: {str(e)}', 'error')
        return redirect(url_for('research.view_checklist_session_summary', session_id=session.id))

    # --- GET Request Logic ---
    # Prepare all data needed for rendering the template

    # 1. Get all checklist items in their correct hierarchical order
    all_ordered_items = get_all_ordered_items_for_checklist(session.checklist_id)
    
    # 2. Fetch all answers for this session just once
    answers_for_session = ResearchAnswer.query.filter_by(research_session_id=session.id).all()
    
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

    # 6. Render the template, passing all the prepared data
    return render_template(
        'session_summary.html',
        title=f"Checklist Summary: {session.company.name}", # Use the company name in the title
        session=session,
        all_ordered_items=all_ordered_items,
        answers_map=answers_map,
        intrinsic_display_value=intrinsic_display_value,
        intrinsic_unit=intrinsic_unit,
        research_context=research_context  # Pass research workflow context
    )

@research_bp.route('/session/<int:session_id>/export/txt')
@login_required
def export_session_to_txt(session_id):
    # 1. Fetch session and authorize user
    session = ResearchSession.query.get_or_404(session_id)
    if session.researcher != current_user:
        flash('You are not authorized to export this research session.', 'error')
        return redirect(url_for('research_workflow.my_projects'))

    # 2. Gather all necessary data
    all_ordered_items = get_all_ordered_items_for_checklist(session.checklist_id)
    answers_for_session = ResearchAnswer.query.filter_by(research_session_id=session.id).all()
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
        export_content.append(session.conclusion)
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
            answer_text = answer_obj.answer_text if answer_obj.answer_text else "No text provided."
            export_content.append(f"{indent}  - **Status:** {status}")
            export_content.append(f"{indent}  - **Answer:** {answer_text}")
        else:
            export_content.append(f"{indent}  - **Status:** Not Answered")

    # 4. Join the content and prepare the file for download
    final_text = "\n".join(export_content)

    safe_company_name = "".join(c if c.isalnum() else "_" for c in session.company.name)
    filename = f"Research_{safe_company_name}_{session_id}.md" # Save as Markdown for nice formatting

    return Response(
        final_text,
        mimetype="text/markdown",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )


@research_bp.route('/task_status/<task_id>')
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

@research_bp.route('/for_company/<int:company_id>/select_model')
@login_required
def select_model(company_id):
    company = Company.query.get_or_404(company_id)
    if company.user_id != current_user.id:
        flash("You are not authorized to access this company.", "error")
        return redirect(url_for('companies.companies_dashboard'))

    # NEW: Check if there is at least one completed research session for this company
    has_completed_research = ResearchSession.query.filter_by(
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
    
    has_porters_analysis = QualitativeAnalysis.query.filter_by(
        user_id=current_user.id,
        company_id=company.id,
        model_type='PortersFiveForces'
    ).first() is not None

    return render_template('select_model.html',
                           company=company,
                           has_completed_research=has_completed_research, # Pass this flag to the template
                           has_swot_analysis=has_swot_analysis, # Pass this flag to the template
                           has_porters_analysis=has_porters_analysis, # Pass this flag to the template
                           title=f"Select Analysis Model for {company.name}")