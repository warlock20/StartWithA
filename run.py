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
    with app.app_context():
        # 1. Enable the vector extension first
        try:
            db.session.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            db.session.commit()
            print("✅ Enabled pgvector extension")
        except Exception as e:
            print(f"⚠️ Warning: Could not enable pgvector. Ensure your DB supports it. Error: {e}")
            db.session.rollback()

        # 2. Now it's safe to create tables that use the VECTOR type
        db.drop_all()
        db.create_all()
    print("Initialized the database.")


if __name__ == '__main__':
    app.run(debug=True)