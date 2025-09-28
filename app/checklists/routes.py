from flask import render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename
import os
import asyncio
from datetime import datetime
from app import db
from app.utils.time_utils import now_utc
from app.models import User, Checklist, ChecklistItem, Company, QuestionBankItem, DocumentImport
from app.checklists import checklists_bp # Import the new blueprint
from app.services.llm_service import (
    LLMChecklistProcessor,
    DocumentParser,
    LLMProvider,
    ProcessingApproach,
    get_available_providers,
    get_supported_file_types
)


@checklists_bp.route('/')
@checklists_bp.route('/checklists', methods=['GET'])
@login_required 
def list_checklists():
    # Show checklists for the currently logged-in user
    checklists = Checklist.query.filter_by(user_id=current_user.id).order_by(Checklist.name).all()
    return render_template('list_checklists.html', checklists=checklists, title=f"Investment Checklists")

@checklists_bp.route('/checklists/new', methods=['GET', 'POST'])
@login_required
def new_checklist():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        starter_template = request.form.get('starter_template')

        if not name:
            flash('Checklist name is required!', 'error')
            return redirect(url_for('checklists.new_checklist'))

        # Create the basic checklist
        new_checklist_obj = Checklist(name=name, description=description, author=current_user)
        db.session.add(new_checklist_obj)

        # Flush to get the checklist ID
        db.session.flush()

        # Add template items if selected
        if starter_template:
            _add_template_items(new_checklist_obj, starter_template)

        try:
            db.session.commit()
            flash('Checklist created successfully! Now add your questions and items.', 'success')
            # Redirect to edit mode for better item building experience
            return redirect(url_for('checklists.view_checklist', checklist_id=new_checklist_obj.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating checklist: {str(e)}', 'error')
            return redirect(url_for('checklists.new_checklist'))

    # For GET request - render the simplified template
    return render_template('new_checklist_simple.html', title="Create New Checklist")


def _add_template_items(checklist, template_type):
    """Add predefined template items to a checklist"""
    templates = {
        'basic_analysis': [
            'Business Model & Strategy',
            'Financial Performance Review',
            'Management Quality Assessment',
            'Competitive Position Analysis',
            'Valuation & Investment Decision'
        ],
        'financial_deep_dive': [
            'Income Statement Analysis',
            'Balance Sheet Review',
            'Cash Flow Statement Analysis',
            'Financial Ratio Analysis',
            'Historical Performance Trends'
        ],
        'competitive_analysis': [
            'Market Position Assessment',
            'Competitive Advantages (Moats)',
            'Industry Structure Analysis',
            'Competitive Threats Evaluation',
            'Market Share & Growth Dynamics'
        ],
        'risk_assessment': [
            'Business Risk Evaluation',
            'Financial Risk Analysis',
            'Market & Economic Risks',
            'Regulatory & Legal Risks',
            'Management & Operational Risks'
        ],
        'value_investing': [
            'Economic Moat Analysis',
            'Financial Strength Check',
            'Management Track Record',
            'Intrinsic Value Calculation',
            'Margin of Safety Assessment'
        ],
        'growth_investing': [
            'Total Addressable Market (TAM)',
            'Revenue Growth Analysis',
            'Unit Economics & Scalability',
            'Competitive Positioning',
            'Growth Sustainability Factors'
        ]
    }

    items = templates.get(template_type, [])
    for i, item_text in enumerate(items):
        item = ChecklistItem(
            text=item_text,
            checklist=checklist,
            parent_id=None,
            order=i
        )
        db.session.add(item)


@checklists_bp.route('/checklists/new/old', methods=['GET', 'POST'])
@login_required
def new_checklist_simple():
    # Initialize question bank data for both GET and POST
    questions_by_sector = {}
    total_questions = 0

    try:
        # Get questions from Question Bank for template
        bank_items = QuestionBankItem.query.filter_by(user_id=current_user.id).all()
        for item in bank_items:
            sector = item.sector or 'General'
            if sector not in questions_by_sector:
                questions_by_sector[sector] = []
            questions_by_sector[sector].append(item)
        total_questions = len(bank_items)
    except Exception as e:
        # If there's any issue with question bank, just continue without it
        print(f"Warning: Could not load question bank: {e}")

    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')

        if not name:
            flash('Checklist name is required!', 'error')
            # For GET request after error, redirect to GET to clear form method
            return redirect(url_for('checklists.new_checklist')) 

        new_checklist_obj = Checklist(name=name, description=description, author=current_user)
        db.session.add(new_checklist_obj)
        # It's often better to commit the parent object (checklist) first, 
        # or commit everything at the end. Let's commit at the end for this block.

        # Get form data for multi-level items
        item_texts = request.form.getlist('item_text[]')
        llm_prompts_for_items = request.form.getlist('item_llm_prompt[]')
        item_levels = request.form.getlist('item_level[]')
        item_paths = request.form.getlist('item_path[]')
        parent_paths = request.form.getlist('parent_path[]')
        priorities = request.form.getlist('item_priority[]')

        # Create a mapping to store created items by their path
        created_items_by_path = {}

        # Debug: Print form data to understand what we're receiving
        print(f"DEBUG: item_texts = {item_texts}")
        print(f"DEBUG: item_levels = {item_levels}")
        print(f"DEBUG: item_paths = {item_paths}")
        print(f"DEBUG: parent_paths = {parent_paths}")
        print(f"DEBUG: priorities = {priorities}")

        # Check if we have any items to process
        if not item_texts or not any(text.strip() for text in item_texts):
            flash('Please add at least one item to your checklist.', 'warning')
            return render_template('new_checklist.html',
                                 title="New Checklist",
                                 name=name,
                                 description=description,
                                 questions_by_sector=questions_by_sector,
                                 total_questions=total_questions)

        # Process items level by level to ensure parents are created before children
        max_level = 0
        if item_levels:
            try:
                max_level = max(int(level) for level in item_levels if level.strip().isdigit())
            except (ValueError, TypeError):
                max_level = 0

        # Process each level in order
        for current_level in range(max_level + 1):
            for i, text in enumerate(item_texts):
                if not text.strip():
                    continue

                # Get item properties with safe defaults
                try:
                    level = int(item_levels[i]) if i < len(item_levels) and item_levels[i].strip().isdigit() else 0
                except (ValueError, TypeError, IndexError):
                    level = 0

                if level != current_level:
                    continue

                item_path = item_paths[i] if i < len(item_paths) else f"{i+1}"
                parent_path = parent_paths[i] if i < len(parent_paths) else ""

                llm_prompt_text = None
                if i < len(llm_prompts_for_items) and llm_prompts_for_items[i].strip():
                    llm_prompt_text = llm_prompts_for_items[i].strip()

                # Determine parent
                parent_item = None
                if parent_path and parent_path in created_items_by_path:
                    parent_item = created_items_by_path[parent_path]

                # Determine order within the same parent/level
                if parent_item:
                    existing_count = ChecklistItem.query.filter_by(
                        checklist_id=new_checklist_obj.id,
                        parent_id=parent_item.id
                    ).count()
                    order = existing_count
                else:
                    # Top-level item
                    existing_count = ChecklistItem.query.filter_by(
                        checklist_id=new_checklist_obj.id,
                        parent_id=None
                    ).count()
                    order = existing_count

                # Create the item
                item = ChecklistItem(
                    text=text.strip(),
                    checklist=new_checklist_obj,
                    parent_id=parent_item.id if parent_item else None,
                    order=order,
                    llm_prompt=llm_prompt_text
                )

                db.session.add(item)
                print(f"DEBUG: Created item '{text.strip()}' at level {level}, order {order}")

                # Store in our path mapping for future children
                created_items_by_path[item_path] = item

        # Flush to ensure all items have IDs
        db.session.flush()

        try:
            db.session.commit() # Commit checklist and all its initial items
            flash('Checklist created successfully!', 'success')
            return redirect(url_for('checklists.view_checklist', checklist_id=new_checklist_obj.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating checklist: {str(e)}', 'error')
            # Re-render form with submitted values to allow correction
            return render_template('new_checklist.html', title="New Checklist", 
                                   name=name, description=description, 
                                   item_texts=item_texts, llm_prompts_for_items=llm_prompts_for_items)


    # For GET request - render the template

    return render_template('new_checklist.html', title="New Checklist",
                           questions_by_sector=questions_by_sector,
                           total_questions=total_questions)

@checklists_bp.route('/<int:checklist_id>/view')
@login_required
def view_readonly_checklist(checklist_id):
    checklist = Checklist.query.get_or_404(checklist_id)
    if checklist.user_id != current_user.id:
        flash('You are not authorized to view this checklist.', 'error')
        return redirect(url_for('checklists.list_checklists'))

    top_level_items = checklist.items.filter_by(parent_id=None).order_by(ChecklistItem.order).all()
    user_companies = Company.query.filter_by(user_id=current_user.id).order_by(Company.name).all()
    
    return render_template(
        'view_readonly_checklist.html',
        checklist=checklist,
        items=top_level_items,
        title=checklist.name,
        ChecklistItem=ChecklistItem,
        companies=user_companies 
    )

@checklists_bp.route('/checklist_item/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_checklist_item(item_id):
    item_to_delete = ChecklistItem.query.get_or_404(item_id)

    # Authorization: Ensure the item belongs to a checklist owned by the current user
    checklist = item_to_delete.checklist # Access the parent checklist
    if checklist.user_id != current_user.id: # Or checklist.author != current_user
        flash('You are not authorized to delete items from this checklist.', 'error')
        # Redirect to a safe page, perhaps the checklists list or an error page
        return redirect(url_for('checklists.list_checklists'))

    # Store checklist_id for redirection before deleting the item
    parent_checklist_id = item_to_delete.checklist_id

    try:
        # First, delete any research answers that reference this item and its children
        from app.models import ResearchAnswer

        def delete_item_and_children_answers(item):
            """Recursively delete research answers for item and its children"""
            # Delete research answers for this item
            ResearchAnswer.query.filter_by(checklist_item_id=item.id).delete()

            # Recursively delete research answers for children
            for child in item.children:
                delete_item_and_children_answers(child)

        # Delete all research answers for this item and its children
        delete_item_and_children_answers(item_to_delete)

        # Commit the research answer deletions first
        db.session.commit()

        # Now we can safely delete the checklist item
        # SQLAlchemy will handle deleting child/sub-items due to
        # cascade="all, delete-orphan" on the ChecklistItem.children relationship.
        db.session.delete(item_to_delete)
        db.session.commit()
        flash('Checklist item and its sub-items deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting checklist item: {str(e)}', 'error')

    return redirect(url_for('checklists.view_checklist', checklist_id=parent_checklist_id))

@checklists_bp.route('/checklist/<int:checklist_id>/delete', methods=['POST'])
@login_required
def delete_checklist(checklist_id):
    checklist = Checklist.query.get_or_404(checklist_id)

    # Authorization: Ensure the checklist belongs to the current user
    if checklist.user_id != current_user.id:
        flash('You are not authorized to delete this checklist.', 'error')
        return redirect(url_for('checklists.list_checklists'))

    try:
        # First, delete any research answers that reference items in this checklist
        from app.models import ResearchAnswer

        # Get all checklist items (including nested ones)
        def get_all_items_recursive(items):
            """Recursively get all items including children"""
            all_items = []
            for item in items:
                all_items.append(item)
                all_items.extend(get_all_items_recursive(item.children))
            return all_items

        all_checklist_items = get_all_items_recursive(checklist.items)

        # Delete all research answers for all items in this checklist
        for item in all_checklist_items:
            ResearchAnswer.query.filter_by(checklist_item_id=item.id).delete()

        # Delete any research sessions that reference this checklist
        from app.models import ResearchSession
        ResearchSession.query.filter_by(checklist_id=checklist.id).delete()

        # Commit the research data deletions first
        db.session.commit()

        # Now we can safely delete the checklist (SQLAlchemy will handle cascade deletion of items)
        db.session.delete(checklist)
        db.session.commit()
        flash(f'Checklist "{checklist.name}" deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting checklist: {str(e)}', 'error')

    return redirect(url_for('checklists.list_checklists'))
    
@checklists_bp.route('/checklists/<int:checklist_id>', methods=['GET'])
@login_required
def view_checklist(checklist_id):
    checklist = Checklist.query.get_or_404(checklist_id)
    if checklist.author != current_user: # Authorization check
        flash('You are not authorized to view this checklist.', 'error')
        return redirect(url_for('checklists.list_checklists'))
    top_level_items = checklist.items.filter_by(parent_id=None).order_by(ChecklistItem.order).all()
    user_companies = Company.query.filter_by(user_id=current_user.id).order_by(Company.name).all()
    total_items_count = checklist.items.count()
    
    # Check if this checklist is being accessed from a research workflow
    from flask import session as flask_session
    research_context = flask_session.get('research_context')

    # Get Question Bank items for integration
    question_bank_items = QuestionBankItem.query.filter_by(user_id=current_user.id).order_by(QuestionBankItem.sector, QuestionBankItem.text).all()

    # Group questions by sector for better organization
    questions_by_sector = {}
    for item in question_bank_items:
        sector = item.sector if item.sector else "General"
        if sector not in questions_by_sector:
            questions_by_sector[sector] = []
        questions_by_sector[sector].append(item)

    return render_template(
        'view_checklist.html',
        checklist=checklist,
        items=top_level_items,
        research_context=research_context,
        title=checklist.name,
        ChecklistItem=ChecklistItem,
        companies=user_companies,
        total_items_count=total_items_count,
        questions_by_sector=questions_by_sector,
        total_questions=len(question_bank_items)
    )
    
# In app/checklists/routes.py

@checklists_bp.route('/<int:checklist_id>/add_item', methods=['POST'])
@login_required
def add_checklist_item(checklist_id):
    checklist = Checklist.query.get_or_404(checklist_id)
    if checklist.user_id != current_user.id:
        flash('You are not authorized to modify this checklist.', 'error')
        return redirect(url_for('checklists.list_checklists'))

    item_text = request.form.get('item_text')
    parent_id_str = request.form.get('parent_id')
    llm_prompt_text = request.form.get('llm_prompt')
    parent_id = None

    if parent_id_str and parent_id_str.strip() and parent_id_str.isdigit():
        parent_id = int(parent_id_str)
        # Verify the parent item belongs to the same checklist
        parent_item_check = ChecklistItem.query.filter_by(id=parent_id, checklist_id=checklist.id).first()
        if not parent_item_check:
            flash('Invalid parent item selected.', 'error')
            return redirect(url_for('checklists.view_checklist', checklist_id=checklist_id))

    if item_text and item_text.strip():
        # Correctly find the maximum order value among the item's siblings
        # A sub-item's siblings have the same parent_id.
        # A top-level item's siblings have parent_id=None.
        max_order = db.session.query(db.func.max(ChecklistItem.order)).filter_by(
            checklist_id=checklist.id,
            parent_id=parent_id
        ).scalar()
        
        # The new order is one greater than the current max, or 0 if no siblings exist.
        new_order = (max_order or -1) + 1
        
        new_item = ChecklistItem(
            text=item_text.strip(), 
            checklist_id=checklist.id, 
            parent_id=parent_id, 
            order=new_order,
            llm_prompt=llm_prompt_text.strip() if llm_prompt_text and llm_prompt_text.strip() else None
        )
        db.session.add(new_item)
        db.session.commit()
        flash('Item added successfully!', 'success')
    else:
        flash('Item text cannot be empty.', 'error')
        
    return redirect(url_for('checklists.view_checklist', checklist_id=checklist.id))


# In app/checklists/routes.py

@checklists_bp.route('/item/<int:item_id>/move/<direction>', methods=['POST'])
@login_required
def move_checklist_item(item_id, direction):
    print(f"\n--- DEBUG: move_checklist_item called for item {item_id}, direction '{direction}' ---")
    item_to_move = ChecklistItem.query.get_or_404(item_id)
    checklist = item_to_move.checklist

    if checklist.user_id != current_user.id:
        flash('You are not authorized to modify this checklist.', 'error')
        return redirect(url_for('checklists.list_checklists'))

    siblings = ChecklistItem.query.filter_by(
        checklist_id=item_to_move.checklist_id,
        parent_id=item_to_move.parent_id
    ).order_by(ChecklistItem.order).all()

    try:
        current_index = siblings.index(item_to_move)
    except ValueError:
        flash('Error finding item in its sibling list.', 'error')
        return redirect(url_for('checklists.view_checklist', checklist_id=checklist.id))

    print(f"DEBUG: Found item '{item_to_move.text}' at index {current_index} with order value {item_to_move.order}")

    swap_successful = False
    if direction == 'up':
        if current_index > 0:
            item_above = siblings[current_index - 1]
            #print(f"DEBUG: Swapping with item above: '{item_above.text}' with order value {item_above.order}")
            item_to_move.order, item_above.order = item_above.order, item_to_move.order
            swap_successful = True
        #else:
            #print("DEBUG: Item is already at the top.")
    elif direction == 'down':
        if current_index < len(siblings) - 1:
            item_below = siblings[current_index + 1]
            #print(f"DEBUG: Swapping with item below: '{item_below.text}' with order value {item_below.order}")
            item_to_move.order, item_below.order = item_below.order, item_to_move.order
            swap_successful = True
        #else:
            #print("DEBUG: Item is already at the bottom.")
    
    if swap_successful:
        #print(f"DEBUG: After swap, item '{item_to_move.text}' has new order value {item_to_move.order}")
        try:
            #print("DEBUG: Calling db.session.commit()...")
            db.session.commit()
            #print("DEBUG: Commit successful.")
            flash(f'Item moved successfully.', 'success')
        except Exception as e:
            db.session.rollback()
            #print(f"DEBUG: Commit FAILED. Error: {e}")
            flash(f'Error saving item order: {str(e)}', 'error')
    
    return redirect(url_for('checklists.view_checklist', checklist_id=checklist.id))


@checklists_bp.route('/item/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_checklist_item(item_id):
    item_to_edit = ChecklistItem.query.get_or_404(item_id)
    checklist = item_to_edit.checklist # Access the parent checklist

    # Authorization: Ensure the item belongs to a checklist owned by the current user
    if checklist.user_id != current_user.id: # Or checklist.author != current_user
        flash('You are not authorized to edit items from this checklist.', 'error')
        return redirect(url_for('checklists.list_checklists'))

    if request.method == 'POST':
        new_text = request.form.get('item_text')
        new_llm_prompt = request.form.get('llm_prompt')

        # Basic validation (you can add more)
        if not new_text or not new_text.strip():
            flash('Item text cannot be empty.', 'error')
            # Re-render the form with submitted values (which the template handles via request.form)
            return render_template('edit_checklist_item.html', title=f"Edit Item: {item_to_edit.text[:30]}...", item=item_to_edit)

        item_to_edit.text = new_text.strip()
        item_to_edit.llm_prompt = new_llm_prompt.strip() if new_llm_prompt and new_llm_prompt.strip() else None

        try:
            db.session.commit()
            flash('Checklist item updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating checklist item: {str(e)}', 'error')

        return redirect(url_for('checklists.view_checklist', checklist_id=checklist.id))

    # GET request: Display the form pre-filled with the item's current data
    return render_template('edit_checklist_item.html',
                           title=f"Edit Item: {item_to_edit.text[:30]}...",
                           item=item_to_edit)


# =====================================
# DOCUMENT IMPORT ROUTES
# =====================================

@checklists_bp.route('/import-document', methods=['GET', 'POST'])
@login_required
def import_document():
    """Handle document import for checklist creation"""

    if request.method == 'GET':
        # Show the import form
        available_providers = get_available_providers()
        supported_file_types = get_supported_file_types()

        return render_template('import_document.html',
                             title="Import Checklist from Document",
                             available_providers=available_providers,
                             supported_file_types=supported_file_types)

    # POST request - handle file upload
    if 'document_file' not in request.files:
        flash('No file selected.', 'error')
        return redirect(request.url)

    file = request.files['document_file']
    if file.filename == '':
        flash('No file selected.', 'error')
        return redirect(request.url)

    # Get form data
    llm_provider = request.form.get('llm_provider', 'openai')
    processing_approach = request.form.get('processing_approach', 'interactive')

    # Validate inputs
    if llm_provider not in [p.value for p in get_available_providers()]:
        flash('Invalid LLM provider selected.', 'error')
        return redirect(request.url)

    # Save uploaded file
    filename = secure_filename(file.filename)
    file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

    if file_ext not in get_supported_file_types():
        flash(f'Unsupported file type. Supported types: {", ".join(get_supported_file_types())}', 'error')
        return redirect(request.url)

    # Create upload directory if it doesn't exist
    upload_dir = os.path.join(current_app.instance_path, 'uploads', 'documents')
    os.makedirs(upload_dir, exist_ok=True)

    # Save file with unique name
    timestamp = now_utc().strftime('%Y%m%d_%H%M%S')
    unique_filename = f"{current_user.id}_{timestamp}_{filename}"
    file_path = os.path.join(upload_dir, unique_filename)
    file.save(file_path)

    # Create database record
    document_import = DocumentImport(
        user_id=current_user.id,
        filename=filename,
        file_type=file_ext,
        file_size=os.path.getsize(file_path),
        file_path=file_path,
        llm_provider=llm_provider,
        processing_approach=processing_approach,
        status='uploaded'
    )

    db.session.add(document_import)
    db.session.commit()

    # Redirect to processing page
    return redirect(url_for('checklists.process_document', import_id=document_import.id))


@checklists_bp.route('/process-document/<int:import_id>')
@login_required
def process_document(import_id):
    """Process uploaded document"""

    document_import = DocumentImport.query.get_or_404(import_id)

    # Authorization check
    if document_import.user_id != current_user.id:
        flash('Unauthorized access.', 'error')
        return redirect(url_for('checklists.list_checklists'))

    # If already processed, show results
    if document_import.status in ['completed', 'failed']:
        return render_template('document_processing_result.html',
                             title="Document Processing Result",
                             import_record=document_import)

    # Start processing
    try:
        document_import.status = 'processing'
        document_import.processed_at = now_utc()
        db.session.commit()

        # Extract text from document
        text_content = DocumentParser.extract_text(
            document_import.file_path,
            document_import.file_type
        )

        document_import.raw_text = text_content
        db.session.commit()

        # Process with LLM
        provider = LLMProvider(document_import.llm_provider)
        approach = ProcessingApproach(document_import.processing_approach)

        processor = LLMChecklistProcessor(provider)

        # Run async processing
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                processor.process_document(text_content, approach)
            )
        finally:
            loop.close()

        # Update document import with results
        document_import.processing_time = result.processing_time

        if result.success:
            document_import.status = 'completed'
            document_import.processed_items = [
                {
                    'text': item.text,
                    'llm_prompt': item.llm_prompt,
                    'category': item.category,
                    'confidence': item.confidence,
                    'parent_id': item.parent_id,
                    'order': item.order
                }
                for item in result.items
            ]
            document_import.suggested_name = result.suggested_name
            document_import.suggested_description = result.suggested_description
        else:
            document_import.status = 'failed'
            document_import.error_message = result.error_message

        document_import.completed_at = now_utc()
        db.session.commit()

    except Exception as e:
        document_import.status = 'failed'
        document_import.error_message = str(e)
        document_import.completed_at = now_utc()
        db.session.commit()

        flash(f'Processing failed: {str(e)}', 'error')

    return render_template('document_processing_result.html',
                         title="Document Processing Result",
                         import_record=document_import)


@checklists_bp.route('/create-from-import/<int:import_id>', methods=['GET', 'POST'])
@login_required
def create_from_import(import_id):
    """Create checklist from processed document import"""

    document_import = DocumentImport.query.get_or_404(import_id)

    # Authorization check
    if document_import.user_id != current_user.id:
        flash('Unauthorized access.', 'error')
        return redirect(url_for('checklists.list_checklists'))

    if document_import.status != 'completed':
        flash('Document processing not completed.', 'error')
        return redirect(url_for('checklists.process_document', import_id=import_id))

    if request.method == 'GET':
        # Show interactive editing interface for Approach C
        if document_import.processing_approach == 'interactive':
            return render_template('create_from_import_interactive.html',
                                 title="Review and Create Checklist",
                                 import_record=document_import)
        # For immediate approach, fall through to POST logic to create checklist directly

    # POST request - create the checklist
    if document_import.processing_approach == 'interactive':
        # Get edited items from form
        name = request.form.get('name', document_import.suggested_name)
        description = request.form.get('description', document_import.suggested_description)

        # Parse selected items (implementation depends on UI design)
        selected_items = request.form.getlist('selected_items[]')
        item_texts = request.form.getlist('item_texts[]')
        item_prompts = request.form.getlist('item_prompts[]')

        # Create checklist with selected/edited items
        # (Implementation details here)

    else:
        # Immediate approach - use all suggested items
        name = document_import.suggested_name
        description = document_import.suggested_description

    # Ensure fields don't exceed database limits
    if name and len(name) > 117:
        name = name[:117] + "..."

    if description and len(description) > 997:
        description = description[:997] + "..."

    # Create the checklist
    new_checklist = Checklist(
        name=name,
        description=description,
        author=current_user
    )
    db.session.add(new_checklist)
    db.session.flush()  # Get the ID

    # Create checklist items
    for item_data in document_import.processed_items:
        if item_data.get('parent_id') is None:  # Top-level items only for now
            checklist_item = ChecklistItem(
                text=item_data['text'],
                checklist_id=new_checklist.id,
                order=item_data.get('order', 0),
                llm_prompt=item_data.get('llm_prompt')
            )
            db.session.add(checklist_item)

    # Link the import to the created checklist
    document_import.created_checklist_id = new_checklist.id
    db.session.commit()

    flash(f'Checklist "{name}" created successfully from document!', 'success')
    return redirect(url_for('checklists.view_checklist', checklist_id=new_checklist.id))


@checklists_bp.route('/import-history')
@login_required
def import_history():
    """Show user's document import history"""

    imports = DocumentImport.query.filter_by(user_id=current_user.id)\
                                 .order_by(DocumentImport.created_at.desc())\
                                 .all()

    return render_template('import_history.html',
                         title="Document Import History",
                         imports=imports)