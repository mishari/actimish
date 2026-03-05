# Deployment on Opalstack

This guide walks through deploying Actimish on Opalstack using uWSGI.

## Opalstack Architecture

Opalstack uses **uWSGI** to run Python WSGI apps. Key points:
- App directory: `/home/actimish/apps/actimish`
- uWSGI config: `uwsgi.ini`
- Code is served from: `myapp/` subdirectory
- Logs: `/home/actimish/logs/apps/actimish/uwsgi.log`
- PID file: `/home/actimish/apps/actimish/tmp/actimish.pid`

## Initial Setup (One-time)

### 1. SSH into Opalstack
```bash
ssh actimish@opal16.opalstack.com
cd /home/actimish/apps/actimish
```

### 2. Clone the repo (if not already done)
```bash
git clone https://github.com/mishari/actimish.git .
```

### 3. Create and activate virtualenv
```bash
python3 -m venv env
source env/bin/activate
```

### 4. Install dependencies

**Important**: Opalstack's GCC 4.8.2 lacks C++11 support. Use pre-compiled wheels for greenlet:

```bash
pip install --only-binary greenlet -r requirements.txt
```

### 5. Run one-time setup
```bash
python setup.py
```
This creates:
- `data/actimish.db` - SQLite database
- `data/secret_key.txt` - Flask secret key
- `data/password.txt` - OAuth login password
- RSA keys in `data/keys/`

### 6. Set environment variables

Create a `.env` file (or set in Opalstack dashboard):
```bash
cat > .env <<EOF
ACTIMISH_DOMAIN=a.mishari.net
ACTIMISH_USERNAME=mishari
ACTIMISH_DISPLAY_NAME=Your Name
ACTIMISH_BIO=Your bio
EOF
```

### 7. Deactivate venv and verify
```bash
deactivate
chmod +x opalstack_deploy.sh
```

### 8. Start the app
```bash
./start
```

## Update Deployment (After pulling code changes)

Run the included deployment script:

```bash
cd /home/actimish/apps/actimish
./opalstack_deploy.sh
```

This script:
1. Stops the app
2. Pulls latest code from GitHub
3. Syncs code into `myapp/` (required by uWSGI config)
4. Installs any new dependencies
5. Restarts the app

### Or manually:

```bash
cd /home/actimish/apps/actimish
./stop

git pull origin main

source env/bin/activate
pip install --only-binary greenlet -r requirements.txt
deactivate

# Sync code to myapp/ (uWSGI expects it there)
rsync -av --delete --exclude='.git' --exclude='env' --exclude='.venv' --exclude='tmp' --exclude='myapp' . myapp/

./start
```

## Verify Deployment

### Check if the app is running
```bash
ps aux | grep uwsgi
# Should show: uwsgi processes bound to 127.0.0.1:21784
```

### Check logs
```bash
tail -f /home/actimish/logs/apps/actimish/uwsgi.log
```

### Test an endpoint
```bash
curl https://a.mishari.net/api/v1/instance
# Should return JSON with instance info
```

### Test WebFinger
```bash
curl https://a.mishari.net/.well-known/webfinger?resource=acct:mishari@a.mishari.net
# Should return actor info
```

## Troubleshooting

### uWSGI won't start
Check logs:
```bash
tail -f /home/actimish/logs/apps/actimish/uwsgi.log
```

Common issues:
- Python import error: `pip install -r requirements.txt` again
- Port in use: Kill with `./kill`, then `./start`
- Database locked: Remove stale `.db-journal` file

### "ImportError: No module named" errors
```bash
source env/bin/activate
pip install --only-binary greenlet -r requirements.txt
deactivate
./stop
./start
```

### Code changes not taking effect
Ensure `myapp/` is synced:
```bash
rsync -av --delete --exclude='.git' --exclude='env' --exclude='.venv' --exclude='tmp' --exclude='myapp' . myapp/
touch myapp/wsgi.py  # uWSGI reloads on touch
```

Or use the deployment script:
```bash
./opalstack_deploy.sh
```

### Data files missing (password.txt, secret_key.txt)
Run setup again:
```bash
source env/bin/activate
python setup.py
deactivate
```

## Files Overview

| File | Purpose |
|------|---------|
| `uwsgi.ini` | uWSGI configuration (Opalstack manages) |
| `opalstack_deploy.sh` | Deployment script (pull + sync + restart) |
| `wsgi.py` | WSGI entry point |
| `app.py` | Flask app factory |
| `setup.py` | One-time setup script |
| `config.py` | Configuration (reads env vars) |
| `myapp/` | Symlinked/synced code (uWSGI reads from here) |
| `data/` | Persistent data (DB, keys, secrets) |
| `env/` | Virtual environment |

## Control Scripts

- `./start` - Start the app (uWSGI daemon)
- `./stop` - Stop the app
- `./kill` - Force-kill stuck processes

## Next Steps

Once deployed and running:

1. **Register a Mastodon client** (e.g., in Tusky):
   - Server: `a.mishari.net`
   - Username: `mishari` (or your `ACTIMISH_USERNAME`)
   - Password: From `data/password.txt`

2. **Verify federation**:
   - Check WebFinger: `curl https://a.mishari.net/.well-known/webfinger?resource=acct:mishari@a.mishari.net`
   - Check ActivityPub actor: `curl https://a.mishari.net/users/mishari`

3. **Monitor**:
   - Tail logs: `tail -f /home/actimish/logs/apps/actimish/uwsgi.log`
   - Check app status: `ps aux | grep uwsgi`
