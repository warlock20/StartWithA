from app.utils.time_utils import parse_date_to_date_object
from flask import render_template, request, redirect, url_for, flash
from flask_login import current_user, login_required
from app import db
from app.models import ( Company, DestinationCheckpoint)
from app.companies import companies_bp

@companies_bp.route('/<int:company_id>/add_checkpoint', methods=['POST'])
@login_required
def add_checkpoint(company_id):
    company = Company.query.get_or_404(company_id)
    # Authorization check
    if company.user_id != current_user.id:
        flash("You are not authorized to modify this company.", "error")
        return redirect(url_for('companies.list_companies'))

    metric = request.form.get('metric')
    expectation = request.form.get('expectation')
    target_date_str = request.form.get('target_date')

    if not metric or not expectation or not target_date_str:
        flash("All fields are required to add a checkpoint.", "error")
        return redirect(url_for('companies.company_dashboard', company_id=company_id))

    try:
        target_date = parse_date_to_date_object(target_date_str)
        if not target_date:
            flash("Invalid date format. Please use YYYY-MM-DD.", "error")
            return redirect(url_for('companies.company_dashboard', company_id=company_id))

        new_checkpoint = DestinationCheckpoint(
            company_id=company.id,
            user_id=current_user.id,
            metric=metric,
            expectation=expectation,
            target_date=target_date
            # Status defaults to 'Active' as defined in the model
        )
        db.session.add(new_checkpoint)
        db.session.commit()
        flash("New destination analysis checkpoint added successfully.", "success")

    except ValueError:
        flash("Invalid date format. Please use YYYY-MM-DD.", "error")
    except Exception as e:
        db.session.rollback()
        flash(f"An error occurred: {e}", "error")

    return redirect(url_for('companies.destination_analysis', company_id=company.id))

@companies_bp.route('/<int:company_id>/destination_analysis')
@login_required
def destination_analysis(company_id):
    company = Company.query.get_or_404(company_id)
    if company.user_id != current_user.id:
        flash("You are not authorized to access this page.", "error")
        return redirect(url_for('companies.list_companies'))

    checkpoints = company.destination_checkpoints.order_by(DestinationCheckpoint.target_date.asc()).all()

    return render_template('destination_analysis.html',
                           company=company,
                           checkpoints=checkpoints,
                           title=f"Destination Analysis for {company.name}",
                           return_url=url_for('companies.company_dashboard', company_id=company.id),
                           context_label=f"{company.name} Dashboard")
    
@companies_bp.route('/checkpoint/<int:checkpoint_id>/update', methods=['POST'])
@login_required
def update_checkpoint(checkpoint_id):
    checkpoint = DestinationCheckpoint.query.get_or_404(checkpoint_id)

    # Authorization check
    if checkpoint.user_id != current_user.id:
        flash("You are not authorized to update this checkpoint.", "error")
        return redirect(url_for('companies.list_companies'))

    # Get data from the form
    new_status = request.form.get('status')
    outcome_notes = request.form.get('outcome_notes')

    # Update the checkpoint object
    checkpoint.status = new_status
    checkpoint.outcome_notes = outcome_notes

    try:
        db.session.commit()
        print(f"  - COMMIT SUCCEEDED. New status in DB should be: '{checkpoint.status}'")
        flash("Checkpoint updated successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating checkpoint: {e}", "error")

    return redirect(url_for('companies.destination_analysis', company_id=checkpoint.company_id)) 

@companies_bp.route('/checkpoint/<int:checkpoint_id>/delete', methods=['POST'])
@login_required
def delete_checkpoint(checkpoint_id):
    checkpoint = DestinationCheckpoint.query.get_or_404(checkpoint_id)

    # Authorization check
    if checkpoint.user_id != current_user.id:
        flash("You are not authorized to delete this checkpoint.", "error")
        return redirect(url_for('companies.list_companies'))

    company_id = checkpoint.company_id # Store for redirect before deleting
    try:
        db.session.delete(checkpoint)
        db.session.commit()
        flash("Checkpoint deleted successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting checkpoint: {e}", "error")

    return redirect(url_for('companies.destination_analysis', company_id=company_id))

@companies_bp.route('/checkpoint/<int:checkpoint_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_checkpoint(checkpoint_id):
    checkpoint = DestinationCheckpoint.query.get_or_404(checkpoint_id)

    # Authorization check
    if checkpoint.user_id != current_user.id:
        flash("You are not authorized to edit this checkpoint.", "error")
        return redirect(url_for('companies.list_companies'))

    if request.method == 'POST':
        # Handle the form submission for updating
        metric = request.form.get('metric')
        expectation = request.form.get('expectation')
        target_date_str = request.form.get('target_date')

        if not metric or not expectation or not target_date_str:
            flash("Metric, Expectation, and Target Date are required.", "error")
            # Re-render the edit form with an error
            return render_template('companies/edit_checkpoint.html', title="Edit Checkpoint", checkpoint=checkpoint)

        parsed_date = parse_date_to_date_object(target_date_str)
        if not parsed_date:
            flash("Invalid date format. Please use YYYY-MM-DD.", "error")
            return render_template('companies/edit_checkpoint.html', title="Edit Checkpoint", checkpoint=checkpoint)

        try:
            checkpoint.metric = metric
            checkpoint.expectation = expectation
            checkpoint.target_date = parsed_date
            db.session.commit()
            flash("Checkpoint updated successfully.", "success")
            return redirect(url_for('companies.destination_analysis', company_id=checkpoint.company_id))
        except Exception as e:
            db.session.rollback()
            flash(f"Error updating checkpoint: {e}", "error")

    # GET request: Show the edit form, pre-filled with existing data
    return render_template('edit_checkpoint.html', 
                           title="Edit Checkpoint", 
                           checkpoint=checkpoint)
