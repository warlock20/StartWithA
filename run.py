from app import create_app, db
from celery_app import celery # Import the celery instance
from app.models import (User, Checklist, ChecklistItem, Company,
                        ChecklistAnalysis, ChecklistAnswer, CompanyDocument)
from sqlalchemy import text

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
        'ChecklistAnalysis': ChecklistAnalysis,
        'ChecklistAnswer': ChecklistAnswer,
        'CompanyDocument': CompanyDocument
    }

@app.cli.command("init-db")
def init_db_command():
    """Clears existing data and creates new tables."""
    # 1. Force enable the extension using a raw connection
    with app.app_context():
        from sqlalchemy import text
        try:
            # Use execution_options to ensure autocommit for extension creation
            with db.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
                connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                print("✅ pgvector extension enabled successfully.")
        except Exception as e:
            print(f"⚠️  Extension check failed: {e}")

        # 2. Now proceed with standard initialization
        db.drop_all()
        db.create_all()
        print("✅ Database initialized and tables created.")


if __name__ == '__main__':
    app.run(debug=True)