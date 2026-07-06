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
PostgreSQL setup script - tries different authentication methods
"""

import os
import subprocess
import psycopg2

def try_create_database():
    """Try different methods to create the PostgreSQL database"""

    print("🔄 Attempting to create PostgreSQL database...")

    # Method 1: Try with system postgres user
    try:
        print("📝 Method 1: Using system postgres user...")
        result = subprocess.run([
            'sudo', '-u', 'postgres', 'psql', '-c',
            "CREATE DATABASE investment_checklist;"
        ], capture_output=True, text=True)

        if result.returncode == 0:
            print("✅ Database created successfully!")
            return True
        else:
            print(f"❌ Failed: {result.stderr}")
    except Exception as e:
        print(f"❌ Method 1 failed: {e}")

    # Method 2: Try with peer authentication
    try:
        print("📝 Method 2: Using peer authentication...")
        conn = psycopg2.connect(
            host="localhost",
            database="postgres",
            user=os.getenv("USER", "postgres")
        )
        conn.autocommit = True
        cursor = conn.cursor()

        # Check if database exists
        cursor.execute("SELECT 1 FROM pg_database WHERE datname='investment_checklist'")
        if not cursor.fetchone():
            cursor.execute("CREATE DATABASE investment_checklist")
            print("✅ Database created successfully!")
        else:
            print("ℹ️  Database already exists!")

        cursor.close()
        conn.close()
        return True

    except Exception as e:
        print(f"❌ Method 2 failed: {e}")

    # Method 3: Manual instructions
    print("\n📋 Manual Setup Required:")
    print("Please run these commands manually:")
    print("1. sudo -u postgres psql")
    print("2. CREATE DATABASE investment_checklist;")
    print("3. \\q")
    print("\nOr configure PostgreSQL authentication for your user.")

    return False

def test_connection():
    """Test connection to the investment_checklist database"""
    connection_strings = [
        f"postgresql://{os.getenv('USER', 'postgres')}@localhost/investment_checklist",
        "postgresql://postgres@localhost/investment_checklist",
        "postgresql://localhost/investment_checklist",
    ]

    print("\n🔍 Testing database connections...")

    for conn_str in connection_strings:
        try:
            print(f"Testing: {conn_str}")
            conn = psycopg2.connect(conn_str)
            conn.close()
            print(f"✅ Connection successful!")

            # Update .env file
            with open('.env', 'r') as f:
                content = f.read()

            content = content.replace(
                "DATABASE_URL='postgresql://localhost/investment_checklist'",
                f"DATABASE_URL='{conn_str}'"
            )

            with open('.env', 'w') as f:
                f.write(content)

            print(f"✅ Updated .env with working connection string")
            return True

        except Exception as e:
            print(f"❌ Failed: {e}")

    return False

if __name__ == "__main__":
    print("🚀 PostgreSQL Setup Script")
    print("=" * 40)

    # Try to create database
    if try_create_database():
        # Test connection
        if test_connection():
            print("\n🎉 PostgreSQL setup complete!")
            print("✅ Database created and connection tested")
            print("🔄 You can now run: flask db upgrade")
        else:
            print("\n⚠️  Database created but connection issues")
    else:
        print("\n❌ Could not create database automatically")
        print("Please create it manually and update DATABASE_URL in .env")