# Deployment on Opalstack

This guide walks through deploying Actimish on Opalstack.

## Prerequisites

- Opalstack account with a Python/WSGI app created
- Domain configured (e.g., `a.mishari.net`)
- SSH access to your Opalstack account

## Opalstack Setup (One-time)

1. **Create a Python/WSGI application** in the Opalstack dashboard:
   - Go to **Applications** → **Create** → **Python/WSGI**
   - Set a name (e.g., `actimish`)
   - Note the app directory path (usually `/home/USERNAME/apps/APPNAME`)

2. **Configure environment variables** in the Opalstack dashboard:
   - Set these in the app's **Environment Variables** section:
     ```
     ACTIMISH_DOMAIN=a.mishari.net
     ACTIMISH_USERNAME=mishari
     ACTIMISH_DISPLAY_NAME=Your Name
     ACTIMISH_BIO=Your bio
     ```

3. **SSH into your Opalstack account**:
   ```bash
   ssh actimish@opal16.opalstack.com
   cd /home/actimish/apps/actimish
   ```

## Initial Deployment

Run these commands **once** to set up the app:

```bash
# Navigate to app directory
cd /home/actimish/apps/actimish

# Clone or pull the repo (first time)
git clone https://github.com/mishari/actimish.git .
# OR if already cloned, pull latest
git pull origin main

# Create and activate virtualenv (if not already done)
python3 -m venv env
source env/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run one-time setup (creates DB, keys, password/secret files)
python setup.py
# This will prompt for password and secret key, storing them in data/

# Deactivate venv
deactivate
```

## Update Deployment (Regularly)

To deploy updated code from GitHub:

```bash
cd /home/actimish/apps/actimish

# Stop the app (if running)
./stop

# Pull latest code
git pull origin main

# Activate venv and install any new deps
source env/bin/activate
pip install -r requirements.txt
deactivate

# Start the app
./start
```

## Configure Opalstack to Run Your App

In the Opalstack **dashboard** for your app:

1. **Start command**: Point to the startup script:
   ```
   /home/actimish/apps/actimish/opalstack_start.sh
   ```

2. Alternatively, use gunicorn directly:
   ```
   /home/actimish/apps/actimish/env/bin/gunicorn wsgi:application --bind 127.0.0.1:PORT --workers 2 --timeout 120
   ```
   (Replace `PORT` with the port assigned by Opalstack, or use 8000)

3. **Restart the application** using the Opalstack dashboard or run:
   ```bash
   ./start
   ```

## Verify Deployment

After starting, check the app:

```bash
# View recent logs
tail -f tmp/actimish.log
# or check Opalstack dashboard logs

# Test a quick endpoint
curl https://a.mishari.net/api/v1/instance

# Check if data files were created
ls -la data/
ls -la data/*.txt  # should see password.txt, secret_key.txt
```

## Troubleshooting

### "Module not found" or import errors
- Ensure `env/bin/python` is being used (check `source env/bin/activate` ran)
- Verify `pip install -r requirements.txt` completed

### Database errors
- Run `python setup.py` again to reinitialize
- Check that `data/` directory is writable: `ls -la data/`

### Port already in use
- Change `PORT` in `opalstack_start.sh` or Opalstack config
- Kill existing process: `./kill`

### Domain not resolving
- Ensure DNS A record points to Opalstack IP
- Check Opalstack dashboard under **Domains**

## Files Overview

- `wsgi.py` - WSGI entry point (what Opalstack calls)
- `opalstack_start.sh` - Startup script with environment loading
- `app.py` - Flask app factory
- `setup.py` - One-time setup script (creates DB, keys, etc.)
- `data/` - Persistent data (created by setup.py, not in git)
  - `secret_key.txt` - Flask secret key
  - `password.txt` - OAuth password
  - `actimish.db` - SQLite database

## Next Steps

Once deployed:
1. Test the instance metadata: `curl https://your-domain/api/v1/instance`
2. Test WebFinger: `curl https://your-domain/.well-known/webfinger?resource=acct:username@domain`
3. Register an app and try logging in with a Mastodon client (e.g., Tusky)
