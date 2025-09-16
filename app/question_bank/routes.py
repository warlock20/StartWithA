from flask import render_template, request, redirect, url_for, flash
from flask_login import current_user, login_required
from app import db
from app.models import QuestionBankItem, SectorAnalysis
from . import question_bank_bp

@question_bank_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        text = request.form.get('text')
        llm_prompt = request.form.get('llm_prompt')
        sector = request.form.get('sector')

        sector_to_save = "General"
        if sector and sector.strip():
            sector_to_save = sector.strip()
            
        if not text:
            flash('Question text is required.', 'error')
        else:
            new_question = QuestionBankItem(
                author=current_user,
                text=text,
                llm_prompt=llm_prompt if llm_prompt else None,
                sector=sector if sector else None
            )
            db.session.add(new_question)
            db.session.commit()
            flash('New question added to your bank.', 'success')
        return redirect(url_for('question_bank.index'))

    # GET Request
    all_questions = QuestionBankItem.query.filter_by(user_id=current_user.id).order_by(QuestionBankItem.text).all()
    
    # Fetch distinct sector names from your research notebooks for the datalist
    existing_sectors_query = db.session.query(SectorAnalysis.sector_name)\
                                        .filter(SectorAnalysis.user_id == current_user.id)\
                                        .distinct().order_by(SectorAnalysis.sector_name).all()
    existing_sectors = [row[0] for row in existing_sectors_query]

    # Process questions into a dictionary grouped by sector (existing logic)
    grouped_questions = {}
    for q in all_questions:
        sector_key = q.sector if q.sector else "General" # This part already handles grouping under "General"
        if sector_key not in grouped_questions:
            grouped_questions[sector_key] = []
        grouped_questions[sector_key].append(q)
        
    return render_template('question_bank.html',
                           title="My Question Bank",
                           grouped_questions=grouped_questions,
                           existing_sectors=existing_sectors,
                           total_questions=len(all_questions))

@question_bank_bp.route('/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_question(item_id):
    question = QuestionBankItem.query.get_or_404(item_id)
    if question.author != current_user:
        flash('You are not authorized to delete this item.', 'error')
        return redirect(url_for('question_bank.index'))

    db.session.delete(question)
    db.session.commit()
    flash('Question deleted from your bank.', 'success')
    return redirect(url_for('question_bank.index'))

@question_bank_bp.route('/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_question(item_id):
    question = QuestionBankItem.query.get_or_404(item_id)
    if question.author != current_user:
        flash('You are not authorized to edit this item.', 'error')
        return redirect(url_for('question_bank.index'))

    if request.method == 'POST':
        text = request.form.get('text')
        llm_prompt = request.form.get('llm_prompt')
        sector = request.form.get('sector')

        if not text or not text.strip():
            flash('Question text is required.', 'error')
        else:
            question.text = text.strip()
            question.llm_prompt = llm_prompt.strip() if llm_prompt and llm_prompt.strip() else None

            sector_to_save = "General"
            if sector and sector.strip():
                sector_to_save = sector.strip()
            question.sector = sector_to_save

            db.session.commit()
            flash('Question updated successfully.', 'success')
            return redirect(url_for('question_bank.index'))

    # GET request: fetch existing sectors for the datalist for a consistent UX
    existing_sectors_query = db.session.query(SectorAnalysis.sector_name)\
                                        .filter(SectorAnalysis.user_id == current_user.id)\
                                        .distinct().order_by(SectorAnalysis.sector_name).all()
    existing_sectors = [row[0] for row in existing_sectors_query]

    return render_template('edit_question.html',
                           title="Edit Question",
                           question=question,
                           existing_sectors=existing_sectors)