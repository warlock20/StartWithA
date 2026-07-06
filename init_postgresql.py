#!/usr/bin/env python3
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

"""
Initialize PostgreSQL database with Flask tables
"""

import os
import sys

def init_flask_db():
    """Initialize Flask database tables"""

    print("🔄 Initializing Flask database...")

    # Add the project directory to Python path
    project_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, project_dir)

    try:
        from app import create_app, db

        # Create Flask app
        app = create_app()

        with app.app_context():
            print("📊 Creating database tables...")

            # Create all tables
            db.create_all()

            print("✅ Database tables created successfully!")

            # Test connection
            result = db.engine.execute("SELECT 1 as test;")
            test_value = result.fetchone()[0]

            if test_value == 1:
                print("✅ Database connection test successful!")
                return True
            else:
                print("❌ Database connection test failed")
                return False

    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        return False

if __name__ == "__main__":
    if init_flask_db():
        print("\n🎉 PostgreSQL initialization complete!")
        print("✅ All tables created")
        print("✅ Connection tested")
        print("🚀 You can now start the Flask application!")
    else:
        print("\n❌ Initialization failed")
        print("Please check the database connection configuration")