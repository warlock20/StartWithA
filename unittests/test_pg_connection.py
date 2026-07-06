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
Test PostgreSQL connection with different WSL configurations
"""

import os
import psycopg2

def test_wsl_postgresql():
    """Test PostgreSQL connections common in WSL environments"""

    # Common WSL PostgreSQL configurations
    test_configs = [
        # Standard configurations
        "postgresql://postgres@localhost/investment_checklist",
        "postgresql://localhost/investment_checklist",
        f"postgresql://{os.getenv('USER')}@localhost/investment_checklist",

        # With explicit ports
        "postgresql://postgres@localhost:5432/investment_checklist",
        "postgresql://localhost:5432/investment_checklist",

        # Unix socket (common in WSL)
        "postgresql:///investment_checklist",

        # If password was set to 'postgres'
        "postgresql://postgres:postgres@localhost/investment_checklist",
        "postgresql://postgres:postgres@localhost:5432/investment_checklist"
    ]

    print("🔍 Testing PostgreSQL connections for WSL environment...")
    print("=" * 50)

    for i, config in enumerate(test_configs, 1):
        try:
            print(f"{i}. Testing: {config}")
            conn = psycopg2.connect(config)

            # Test basic query
            cursor = conn.cursor()
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]

            cursor.close()
            conn.close()

            print(f"   ✅ SUCCESS! PostgreSQL version: {version[:50]}...")
            print(f"   📝 Working connection string: {config}")

            # Update .env file
            env_content = ""
            with open('.env', 'r') as f:
                for line in f:
                    if line.startswith('DATABASE_URL='):
                        env_content += f"DATABASE_URL='{config}'\n"
                    else:
                        env_content += line

            with open('.env', 'w') as f:
                f.write(env_content)

            print(f"   ✅ Updated .env file with working connection")
            return config

        except Exception as e:
            print(f"   ❌ Failed: {str(e)[:60]}...")

    print("\n❌ No working connection found.")
    print("\n💡 WSL PostgreSQL Setup Tips:")
    print("1. Check if PostgreSQL is running: sudo service postgresql status")
    print("2. Start PostgreSQL: sudo service postgresql start")
    print("3. Create database manually: sudo -u postgres createdb investment_checklist")
    print("4. Or configure peer authentication in pg_hba.conf")

    return None

if __name__ == "__main__":
    working_config = test_wsl_postgresql()

    if working_config:
        print(f"\n🎉 PostgreSQL setup complete!")
        print(f"✅ Working connection: {working_config}")
        print("🔄 Next: Run 'flask db upgrade' to create tables")
    else:
        print(f"\n⚠️  Manual setup required")
        print("Please ensure PostgreSQL is running and database exists")