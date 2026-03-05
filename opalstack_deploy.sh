#!/bin/bash
#
# Opalstack deployment script for Actimish
# Run this on your Opalstack account to pull and deploy code
#
# Usage:
#   ./opalstack_deploy.sh
#

set -e

APPDIR="/home/actimish/apps/actimish"
MYAPPDIR="$APPDIR/myapp"

echo "=== Actimish Opalstack Deployment ==="
cd "$APPDIR"

# Stop the app
echo "Stopping app..."
if [ -f "$APPDIR/stop" ]; then
    "$APPDIR/stop"
fi

# Pull latest code from GitHub
echo "Pulling latest code from main..."
git pull origin main

# Copy code into myapp/ (Opalstack expects it there)
echo "Syncing code to myapp/..."
mkdir -p "$MYAPPDIR"
rsync -av --delete --exclude='.git' --exclude='env' --exclude='.venv' --exclude='tmp' --exclude='myapp' \
    "$APPDIR"/ "$MYAPPDIR"/

# Activate virtualenv
echo "Activating virtualenv..."
source "$APPDIR/env/bin/activate"

# Install dependencies (with greenlet pre-compiled to avoid GCC C++11 issue)
echo "Installing dependencies..."
pip install --only-binary greenlet -r "$APPDIR/requirements.txt"

# Run setup if data/ doesn't exist (first-time deployment)
if [ ! -d "$APPDIR/data" ]; then
    echo "First deployment detected. Running setup..."
    cd "$APPDIR"
    python setup.py
else
    echo "Existing deployment detected. Skipping setup."
    echo "Run 'python setup.py' manually if you need to reinitialize."
fi

# Deactivate venv
deactivate

# Start the app
echo "Starting app..."
if [ -f "$APPDIR/start" ]; then
    "$APPDIR/start"
fi

echo "=== Deployment complete ==="
echo ""
echo "Verify deployment:"
echo "  tail -f /home/actimish/logs/apps/actimish/uwsgi.log"
echo ""
echo "Test the instance:"
echo "  curl https://a.mishari.net/api/v1/instance"
