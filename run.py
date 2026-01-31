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
        

# @app.cli.command("init-db")
# def init_db_command():
#     """Wipes database and creates new tables."""
#     with app.app_context():
#         # 1. Enable extension
#         try:
#             with db.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
#                 connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
#                 print("✅ pgvector extension enabled.")
#         except Exception as e:
#             print(f"⚠️ Extension check warning: {e}")

#         # 2. FORCE DROP ALL TABLES
#         # We manually drop tables with CASCADE to bypass the circular dependency error
#         try:
#             inspector = sqlalchemy.inspect(db.engine)
#             tables = inspector.get_table_names()
            
#             if tables:
#                 print(f"🗑️ Found {len(tables)} tables. Dropping with CASCADE...")
#                 with db.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
#                     for table in tables:
#                         # "CASCADE" forces deletion even if other tables link to it
#                         connection.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
#                 print("✅ All tables dropped.")
#             else:
#                 print("ℹ️ Database is already empty.")

#         except Exception as e:
#             print(f"⚠️ Error during drop: {e}")

#         # 3. Create Tables
#         print("🔨 Creating new tables...")
#         try:
#             db.create_all()
#             print("✅ Database initialized successfully!")
#         except Exception as e:
#             print(f"❌ Error creating tables: {e}")


if __name__ == '__main__':
    app.run(debug=True)