from flask import render_template, request, redirect, url_for, flash
from flask_login import current_user, login_required
from app import db
from app.models import SectorAnalysis, QuestionBankItem
from . import sectors_bp

@sectors_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        sector_name = request.form.get('sector_name')
        if not sector_name or not sector_name.strip():
            flash('Sector name is required.', 'error')
            return redirect(url_for('sectors.index'))

        # Check if an analysis for this sector already exists for the user
        existing = SectorAnalysis.query.filter_by(user_id=current_user.id, sector_name=sector_name.strip()).first()
        if existing:
            flash(f'You already have a research notebook for the "{sector_name}" sector.', 'info')
            # Redirect to the existing notebook page (we'll create this route next)
            return redirect(url_for('sectors.notebook', sector_name=existing.sector_name))

        new_analysis = SectorAnalysis(
            author=current_user,
            sector_name=sector_name.strip()
        )
        db.session.add(new_analysis)
        db.session.commit()
        flash(f'New research notebook for "{sector_name}" created.', 'success')
        # Redirect to the new notebook page
        return redirect(url_for('sectors.notebook', sector_name=new_analysis.sector_name))


    # GET Request: Fetch and display all existing sector analyses
    sector_analyses = SectorAnalysis.query.filter_by(user_id=current_user.id).order_by(SectorAnalysis.sector_name).all()

    return render_template('list_sectors.html', 
                           title="My Sector Research",
                           sector_analyses=sector_analyses)
    
@sectors_bp.route('/<string:sector_name>', methods=['GET', 'POST'])
@login_required
def notebook(sector_name):
    # Fetch the main analysis object for this sector
    analysis = SectorAnalysis.query.filter_by(user_id=current_user.id, sector_name=sector_name).first_or_404()

    if request.method == 'POST':
        # This POST handles saving the main notes textarea
        analysis.notes = request.form.get('notes')
        db.session.commit()
        flash('Notes saved successfully.', 'success')
        return redirect(url_for('sectors.notebook', sector_name=analysis.sector_name))

    # GET Request: Fetch questions from the bank that are tagged with this sector
    question_bank_items = QuestionBankItem.query.filter_by(
        user_id=current_user.id,
        sector=sector_name
    ).order_by(QuestionBankItem.created_at.desc()).all()

    return render_template(
        'sector_analysis.html',
        title=f"Research: {analysis.sector_name}",
        analysis=analysis,
        question_bank_items=question_bank_items
    )

@sectors_bp.route('/<string:sector_name>/add_question', methods=['POST'])
@login_required
def add_question_to_bank(sector_name):
    # This route specifically handles adding a new question to the bank from the notebook page
    analysis = SectorAnalysis.query.filter_by(user_id=current_user.id, sector_name=sector_name).first_or_404()

    text = request.form.get('text')
    llm_prompt = request.form.get('llm_prompt')

    if not text:
        flash('Question text is required.', 'error')
    else:
        new_question = QuestionBankItem(
            author=current_user,
            text=text,
            llm_prompt=llm_prompt if llm_prompt else None,
            sector=sector_name # Automatically tag with the current sector
        )
        db.session.add(new_question)
        db.session.commit()
        flash('New question added to your bank for this sector.', 'success')

    return redirect(url_for('sectors.notebook', sector_name=sector_name))

@sectors_bp.route('/question_bank_item/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_question_from_bank(item_id):
    # This route handles deleting a question and redirects back to the notebook page
    question = QuestionBankItem.query.get_or_404(item_id)
    if question.author != current_user:
        flash('You are not authorized to delete this item.', 'error')
        return redirect(url_for('sectors.index'))

    sector_name = question.sector # Get sector name for redirect before deleting
    db.session.delete(question)
    db.session.commit()
    flash('Question deleted from your bank.', 'success')

    # If we came from a sector page, redirect back there. Otherwise, to the main bank.
    if sector_name:
        return redirect(url_for('sectors.notebook', sector_name=sector_name))
    else:
        return redirect(url_for('question_bank.index'))
    
@sectors_bp.route('/<int:analysis_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_sector(analysis_id):
    analysis = SectorAnalysis.query.get_or_404(analysis_id)
    # Authorization check
    if analysis.author != current_user:
        flash("You are not authorized to edit this sector analysis.", "error")
        return redirect(url_for('sectors.index'))

    if request.method == 'POST':
        old_sector_name = analysis.sector_name
        new_sector_name = request.form.get('sector_name', '').strip()

        if not new_sector_name:
            flash("Sector name cannot be empty.", "error")
            return render_template('edit_sector.html', title="Edit Sector", analysis=analysis)

        # Check if a notebook with the new name already exists for this user
        existing = SectorAnalysis.query.filter(
            SectorAnalysis.user_id == current_user.id,
            SectorAnalysis.sector_name == new_sector_name,
            SectorAnalysis.id != analysis.id # Exclude the current one
        ).first()

        if existing:
            flash(f"You already have a research notebook named '{new_sector_name}'.", "error")
            return render_template('edit_sector.html', title="Edit Sector", analysis=analysis)

        # --- Update the Question Bank Items ---
        # Find all questions tagged with the old sector name and update them
        QuestionBankItem.query.filter_by(user_id=current_user.id, sector=old_sector_name)\
                              .update({'sector': new_sector_name})

        # Update the analysis object itself
        analysis.sector_name = new_sector_name

        try:
            db.session.commit()
            flash("Sector analysis updated successfully.", "success")
            # Redirect to the notebook page with the NEW name
            return redirect(url_for('sectors.notebook', sector_name=new_sector_name))
        except Exception as e:
            db.session.rollback()
            flash(f"An error occurred: {e}", "error")
        
        next_url = request.args.get('next')
        if next_url:
            return redirect(next_url)
        else:
            return redirect(url_for('question_bank.index'))

    # GET request
    return render_template('edit_sector.html', title="Edit Sector", analysis=analysis)        