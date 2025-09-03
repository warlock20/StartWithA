from flask import render_template, request, redirect, url_for, flash
from flask_login import current_user, login_required
from app import db
from app.models import JournalEntry, Company
from . import journal_bp

@journal_bp.route('/', methods=['GET', 'POST'])
@login_required
def index(company_id):
    company = Company.query.get_or_404(company_id)
    if company.user_id != current_user.id:
        flash("You are not authorized to access this journal.", "error")
        return redirect(url_for('companies.list_companies'))

    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        tags = request.form.get('tags')

        if not title:
            flash("Entry title is required.", "error")
        else:
            new_entry = JournalEntry(
                company_id=company_id,
                user_id=current_user.id,
                title=title,
                content=content,
                tags=tags
            )
            db.session.add(new_entry)
            db.session.commit()
            flash("New journal entry saved.", "success")
        return redirect(url_for('journal.index', company_id=company_id))

    # GET Request: Fetch and display all journal entries for this company
    journal_entries = company.journal_entries.order_by(JournalEntry.entry_date.desc()).all()

    return render_template('journal.html', 
                           title=f"Research Journal for {company.name}",
                           company=company,
                           journal_entries=journal_entries)