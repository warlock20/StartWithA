#!/bin/bash
set -e

echo "Running database setup..."

# If alembic_version is empty/missing, stamp at head so future migrations work.
python -c "
from run import app
from sqlalchemy import text
with app.app_context():
    engine = app.extensions['migrate'].db.engine
    with engine.connect() as conn:
        try:
            result = conn.execute(text('SELECT version_num FROM alembic_version'))
            row = result.fetchone()
            if row is None:
                print('NEEDS_STAMP')
            else:
                print('HAS_VERSION: ' + row[0])
        except Exception:
            print('NEEDS_STAMP')
" 2>&1 | grep -q "NEEDS_STAMP" && {
    echo "No alembic version found. Stamping at head..."
    flask db stamp head
}

echo "Running migrations..."
flask db upgrade

echo "Starting application..."
exec gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 120 run:app
