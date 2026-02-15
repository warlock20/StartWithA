#!/bin/bash
set -e

echo "Running database migrations..."
# If alembic_version table is empty/missing, stamp to the last known-good revision
# so Alembic doesn't try to replay all migrations from scratch.
# b8bd4bcb76e4 = last migration before is_admin (all prior migrations already applied)
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
    echo "No alembic version found. Stamping database at b8bd4bcb76e4..."
    flask db stamp b8bd4bcb76e4
}

flask db upgrade

echo "Starting application..."
exec gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 120 run:app
