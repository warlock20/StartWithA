#!/usr/bin/env python3
"""
Database Sync Utility - Railway to Local

Safely pull production data from Railway to your local PostgreSQL database.

Setup (one-time):
    1. In Railway dashboard → pgvector service → Settings → Networking
       → Enable "Public Networking" (TCP Proxy)
    2. Copy the public host and port (e.g., roundhouse.proxy.rlwy.net:12345)
    3. Add to your .env file:
       RAILWAY_DB_PUBLIC_URL=postgresql://postgres:postgres@roundhouse.proxy.rlwy.net:12345/investment_platform

Usage:
    python sync_db.py pull     # Pull Railway data to local
    python sync_db.py export   # Export Railway data to a file
    python sync_db.py check    # Verify connection
"""

import os
import sys
import subprocess
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Local database
LOCAL_DB_URL = os.getenv(
    'DATABASE_URL',
    'postgresql://postgres:postgres@localhost:5432/investment_checklist'
)

# Railway database (public TCP proxy URL)
RAILWAY_DB_URL = os.getenv('RAILWAY_DB_PUBLIC_URL')


def run_command(cmd, error_msg="Command failed"):
    """Run shell command and return stdout."""
    print(f"  → {' '.join(cmd[:4])}...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ✗ {error_msg}")
        if result.stderr:
            # Show only the last meaningful line of error
            for line in result.stderr.strip().splitlines():
                if line.strip():
                    print(f"    {line.strip()}")
        return None
    return result.stdout


def get_railway_url():
    """Get and validate Railway database URL."""
    if not RAILWAY_DB_URL:
        print("✗ RAILWAY_DB_PUBLIC_URL not set in your .env file.\n")
        print("Setup steps:")
        print("  1. Go to Railway dashboard → pgvector service")
        print("  2. Settings → Networking → Enable 'Public Networking'")
        print("  3. Copy the public host:port (e.g., roundhouse.proxy.rlwy.net:12345)")
        print("  4. Add to .env:")
        print("     RAILWAY_DB_PUBLIC_URL=postgresql://postgres:postgres@<host>:<port>/investment_platform")
        sys.exit(1)
    return RAILWAY_DB_URL


def check_connection():
    """Verify connection to both local and Railway databases."""
    print("\n=== Connection Check ===\n")

    # Check local
    print("Local database:")
    result = run_command([
        'psql', LOCAL_DB_URL, '-t', '-c', 'SELECT current_database();'
    ], "Cannot connect to local database")
    if result:
        print(f"  ✓ Connected to: {result.strip()}")

    # Check Railway
    print("\nRailway database:")
    railway_url = get_railway_url()
    result = run_command([
        'psql', railway_url, '-t', '-c', 'SELECT current_database();'
    ], "Cannot connect to Railway database")
    if result:
        print(f"  ✓ Connected to: {result.strip()}")
        # Count users
        result = run_command([
            'psql', railway_url, '-t', '-c', 'SELECT COUNT(*) FROM "user";'
        ], "Could not count users")
        if result:
            print(f"  ✓ Users in Railway: {result.strip()}")

    print("\n✓ All connections look good!")


def export_railway_db(output_file):
    """Export Railway database to a SQL file."""
    print(f"\n=== Exporting Railway Database ===\n")

    railway_url = get_railway_url()

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    if output_file == 'auto':
        output_file = f'railway_backup_{timestamp}.sql'

    print(f"Exporting to: {output_file}")

    cmd = ['pg_dump', railway_url, '--clean', '--if-exists']

    with open(output_file, 'w') as f:
        result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            print(f"✗ Export failed: {result.stderr}")
            # Cleanup empty file
            if os.path.exists(output_file):
                os.remove(output_file)
            sys.exit(1)

    size_mb = os.path.getsize(output_file) / (1024 * 1024)
    print(f"✓ Exported ({size_mb:.2f} MB): {output_file}")
    return output_file


def pull_from_railway():
    """Pull Railway database to local PostgreSQL."""
    print("\n=== Pulling Railway → Local ===\n")

    # Step 1: Export
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    temp_file = f'/tmp/railway_backup_{timestamp}.sql'

    print("Step 1/4: Exporting Railway database...")
    export_railway_db(temp_file)

    # Step 2: Confirm
    print(f"\n⚠️  This will OVERWRITE your local database!")
    print(f"   Local: {LOCAL_DB_URL}\n")
    response = input("Type 'yes' to proceed: ")

    if response.strip().lower() != 'yes':
        print("Aborted. No changes made.")
        os.remove(temp_file)
        sys.exit(0)

    # Step 3: Reset local schema
    print("\nStep 2/4: Clearing local database...")
    result = run_command([
        'psql', LOCAL_DB_URL,
        '-c', 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'
    ], "Could not reset local database")
    if result is None:
        print(f"\nBackup saved at: {temp_file}")
        sys.exit(1)
    print("  ✓ Local database cleared")

    # Step 4: Import
    print("\nStep 3/4: Importing Railway data...")
    with open(temp_file, 'r') as f:
        result = subprocess.run(
            ['psql', LOCAL_DB_URL],
            stdin=f, capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"  ✗ Import failed: {result.stderr}")
            print(f"\nBackup saved at: {temp_file}")
            sys.exit(1)
    print("  ✓ Data imported")

    # Step 5: Verify
    print("\nStep 4/4: Verifying...")
    count = run_command([
        'psql', LOCAL_DB_URL,
        '-t', '-c', 'SELECT COUNT(*) FROM "user";'
    ], "Could not verify import")
    if count:
        print(f"  ✓ {count.strip()} users in local database")

    # Cleanup temp file
    os.remove(temp_file)

    print("\n" + "=" * 50)
    print("  ✓ SUCCESS! Local database synced with Railway")
    print("=" * 50)
    print("\nRun your app locally to debug with production data:")
    print("  flask run")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == 'pull':
        pull_from_railway()
    elif command == 'export':
        output_file = sys.argv[2] if len(sys.argv) >= 3 else 'auto'
        export_railway_db(output_file)
    elif command == 'check':
        check_connection()
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == '__main__':
    main()
