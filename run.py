from app import create_app, db
from celery_app import celery # Import the celery instance
from app.models import (User, Checklist, ChecklistItem, Company, 
                        ResearchSession, ResearchAnswer, CompanyDocument)

# 1. Create the Flask app instance FIRST.
app = create_app()

# 2. NOW you can use the 'app' variable in decorators.
@app.shell_context_processor
def make_shell_context():
    """Makes additional variables available in the Flask shell context."""
    return {
        'app': app, 
        'db': db, 
        'User': User, 
        'Checklist': Checklist, 
        'ChecklistItem': ChecklistItem,
        'Company': Company,
        'ResearchSession': ResearchSession,
        'ResearchAnswer': ResearchAnswer,
        'CompanyDocument': CompanyDocument
    }

@app.cli.command("init-db")
def init_db_command():
    """Clears existing data and creates new tables."""
    with app.app_context():
        db.drop_all()
        db.create_all()
    print("Initialized the database.")


if __name__ == '__main__':
    app.run(debug=True)