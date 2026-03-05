#!/bin/bash
#
# Opalstack WSGI startup script for Actimish.
#
# On Opalstack, create a "Python/WSGI" application and place this project
# in the app directory. Then configure the start command, or use gunicorn
# directly in the Opalstack dashboard.
#
# Usage:
#   ./opalstack_start.sh
#
# Environment variables (set in Opalstack dashboard or .env):
#   ACTIMISH_DOMAIN      - your domain (e.g., a.mishari.net)
#   ACTIMISH_PASSWORD    - login password for OAuth
#   ACTIMISH_SECRET_KEY  - Flask secret key
#   ACTIMISH_USERNAME    - ActivityPub username (default: mishari)
#

set -e

# Determine script directory
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# Activate virtualenv if present
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "$DIR/../env" ]; then
    source "$DIR/../env/bin/activate"
fi

# Load .env if it exists
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Read secret key from file if env var not set
if [ -z "$ACTIMISH_SECRET_KEY" ] && [ -f "data/secret_key.txt" ]; then
    export ACTIMISH_SECRET_KEY="$(cat data/secret_key.txt)"
fi

# Read password from file if env var not set
if [ -z "$ACTIMISH_PASSWORD" ] && [ -f "data/password.txt" ]; then
    export ACTIMISH_PASSWORD="$(cat data/password.txt)"
fi

# Start gunicorn (Opalstack assigns the port via $PORT or you set it)
PORT="${PORT:-8000}"

exec gunicorn wsgi:application \
    --bind "127.0.0.1:$PORT" \
    --workers 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
