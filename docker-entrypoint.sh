#!/bin/bash
set -e

# Run database migrations if needed
# flask db upgrade

# Execute the main container command (Gunicorn)
exec "$@"
