# company_research_platform/run.py

from app import create_app, db
from app.models import User, Checklist, ChecklistItem # Import your models

# Create the Flask app instance using the factory
app = create_app()

@app.shell_context_processor
def make_shell_context():
    """
    Makes additional variables available in the Flask shell context.
    """
    return {'app': app, 'db': db, 'User': User, 'Checklist': Checklist, 'ChecklistItem': ChecklistItem}

# New: Add a CLI command to initialize the database
@app.cli.command("init-db")
def init_db_command():
    """Clears existing data and creates new tables."""
    with app.app_context(): # Ensure operations are within app context
        db.drop_all()  # Optional: drops all tables first if you want a clean slate
        db.create_all()
    print("Initialized the database.")

if __name__ == '__main__':
    app.run(debug=True)