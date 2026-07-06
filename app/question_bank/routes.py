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

from flask import render_template, request, redirect, url_for, flash
from flask_login import current_user, login_required
from app import db
from app.models import QuestionBankItem, SectorAnalysis
from app.models.sector import Sector
from . import question_bank_bp


@question_bank_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        text = request.form.get('text')
        llm_prompt = request.form.get('llm_prompt')
        sector_name = request.form.get('sector')
        category = request.form.get('category')

        if not text:
            flash('Question text is required.', 'error')
        else:
            # Look up Sector by display_name to get proper FK
            sector_id = None
            if sector_name and sector_name.strip():
                sector_obj = Sector.query.filter_by(
                    display_name=sector_name.strip(),
                    user_id=current_user.id
                ).first()
                if sector_obj:
                    sector_id = sector_obj.id

            new_question = QuestionBankItem(
                user_id=current_user.id,
                text=text,
                llm_prompt=llm_prompt.strip() if llm_prompt and llm_prompt.strip() else None,
                sector_id=sector_id,
                category=category.strip() if category and category.strip() else None,
            )
            db.session.add(new_question)
            db.session.commit()
            flash('New question added to your bank.', 'success')
        return redirect(url_for('question_bank.index'))

    # GET Request
    all_questions = QuestionBankItem.query.filter_by(
        user_id=current_user.id
    ).order_by(QuestionBankItem.text).all()

    # Fetch distinct sector names from user's research notebooks for the datalist
    existing_sectors_query = db.session.query(Sector.display_name)\
                                        .join(SectorAnalysis, Sector.id == SectorAnalysis.sector_id)\
                                        .filter(SectorAnalysis.user_id == current_user.id)\
                                        .distinct().order_by(Sector.display_name).all()
    existing_sectors = [row[0] for row in existing_sectors_query]

    # Group questions by sector display name
    grouped_questions = {}
    for q in all_questions:
        sector_key = q.sector.display_name if q.sector else "General"
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
    if question.user_id != current_user.id:
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
    if question.user_id != current_user.id:
        flash('You are not authorized to edit this item.', 'error')
        return redirect(url_for('question_bank.index'))

    if request.method == 'POST':
        text = request.form.get('text')
        llm_prompt = request.form.get('llm_prompt')
        sector_name = request.form.get('sector')
        category = request.form.get('category')

        if not text or not text.strip():
            flash('Question text is required.', 'error')
        else:
            question.text = text.strip()
            question.llm_prompt = llm_prompt.strip() if llm_prompt and llm_prompt.strip() else None
            question.category = category.strip() if category and category.strip() else None

            # Look up Sector by display_name for proper FK
            if sector_name and sector_name.strip() and sector_name.strip() != "General":
                sector_obj = Sector.query.filter_by(
                    display_name=sector_name.strip(),
                    user_id=current_user.id
                ).first()
                question.sector_id = sector_obj.id if sector_obj else None
            else:
                question.sector_id = None

            db.session.commit()
            flash('Question updated successfully.', 'success')
            return redirect(url_for('question_bank.index'))

    # GET request: fetch existing sectors for the datalist
    existing_sectors_query = db.session.query(Sector.display_name)\
                                        .join(SectorAnalysis, Sector.id == SectorAnalysis.sector_id)\
                                        .filter(SectorAnalysis.user_id == current_user.id)\
                                        .distinct().order_by(Sector.display_name).all()
    existing_sectors = [row[0] for row in existing_sectors_query]

    return render_template('edit_question.html',
                           title="Edit Question",
                           question=question,
                           existing_sectors=existing_sectors)
