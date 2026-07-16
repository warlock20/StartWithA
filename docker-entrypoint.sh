#!/bin/bash
set -e

# Run one-time DB setup only in the web/app container, not in the Celery worker,
# so two containers don't migrate the same database concurrently. The worker
# starts with `celery ...`, the web container with `gunicorn ...`.
if [ "$1" != "celery" ]; then
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
fi

# Run whatever command the service declared:
#   web    -> gunicorn (Dockerfile CMD)
#   worker -> celery ... (docker-compose command)
echo "Starting: $*"
exec "$@"
