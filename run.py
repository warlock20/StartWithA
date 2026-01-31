import os
from app import create_app, db
from sqlalchemy import text
import sqlalchemy

app = create_app()

@app.cli.command("init-db")
def init_db_command():
    """Wipes database and creates new tables."""
    with app.app_context():
        # 1. Enable extension
        try:
            with db.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
                connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                print("✅ pgvector extension enabled.")
        except Exception as e:
            print(f"⚠️ Extension check warning: {e}")

        # 2. FORCE DROP ALL TABLES
        # We manually drop tables with CASCADE to bypass the circular dependency error
        try:
            inspector = sqlalchemy.inspect(db.engine)
            tables = inspector.get_table_names()
            
            if tables:
                print(f"🗑️ Found {len(tables)} tables. Dropping with CASCADE...")
                with db.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
                    for table in tables:
                        # "CASCADE" forces deletion even if other tables link to it
                        connection.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
                print("✅ All tables dropped.")
            else:
                print("ℹ️ Database is already empty.")

        except Exception as e:
            print(f"⚠️ Error during drop: {e}")

        # 3. Create Tables
        print("🔨 Creating new tables...")
        try:
            db.create_all()
            print("✅ Database initialized successfully!")
        except Exception as e:
            print(f"❌ Error creating tables: {e}")

if __name__ == "__main__":
    app.run(debug=True)