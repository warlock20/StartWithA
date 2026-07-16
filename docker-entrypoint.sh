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
#
# Fall back to the web command if invoked with no arguments. This happens when a
# platform (e.g. a Railway dashboard "Custom Start Command") overrides Docker's
# CMD with just `./docker-entrypoint.sh` and passes nothing through — without
# this guard `exec "$@"` would exec nothing and the container would exit.
if [ "$#" -eq 0 ]; then
    set -- gunicorn --bind "0.0.0.0:${PORT:-8000}" --workers 2 --threads 4 \
        --worker-class gthread --timeout 120 --keep-alive 5 --preload run:app
fi

echo "Starting: $*"
exec "$@"
