# Opalstack Initial Setup - Replace Boilerplate with Actimish

Run these commands **on your Opalstack account** to replace the boilerplate with the actual Actimish code.

## SSH into Opalstack

```bash
ssh actimish@opal16.opalstack.com
cd /home/actimish/apps/actimish
```

## Step 1: Backup Opalstack Files (Keep These)

Keep the Opalstack-managed files and remove everything else:

```bash
# Backup the original boilerplate myapp/ (optional, for safety)
mv myapp myapp.backup

# List what you have (should see: env, start, stop, kill, uwsgi.ini, tmp)
ls -la
```

## Step 2: Clone Actimish

Choose one approach:

### Option A: Clone directly into current directory (recommended)

```bash
# Initialize git in current directory
git init
git remote add origin https://github.com/mishari/actimish.git
git fetch origin main
git checkout -b main origin/main
git branch -u origin/main main
```

### Option B: Clone to temp, move files

```bash
git clone https://github.com/mishari/actimish.git actimish_repo

# Move everything from the repo to current directory
mv actimish_repo/* .
mv actimish_repo/.[^.]* . 2>/dev/null || true
rmdir actimish_repo

# Initialize git tracking
git remote set-url origin https://github.com/mishari/actimish.git
```

## Step 3: Verify Git Setup

```bash
git status
git log --oneline -3
```

You should see the Actimish commits.

## Step 4: Install Python Dependencies

**Important**: Opalstack's GCC 4.8.2 lacks C++11 support, so we must use pre-compiled wheels for greenlet:

```bash
source env/bin/activate
pip install --only-binary greenlet -r requirements.txt
deactivate
```

(The `--only-binary greenlet` flag prevents pip from trying to compile greenlet from source, which would fail on old GCC.)

## Step 5: Run One-Time Setup

```bash
source env/bin/activate
python setup.py
```

This creates:
- `data/actimish.db` - SQLite database
- `data/secret_key.txt` - Flask secret key
- `data/password.txt` - OAuth password
- `data/keys/` - RSA keypair for signing

**Important**: Save the password printed to console (or read it from `data/password.txt`).

```bash
deactivate
```

## Step 6: Create .env File (Optional)

If not setting environment variables in Opalstack dashboard:

```bash
cat > .env <<'EOF'
ACTIMISH_DOMAIN=a.mishari.net
ACTIMISH_USERNAME=mishari
ACTIMISH_DISPLAY_NAME=Your Name
ACTIMISH_BIO=Your bio
EOF
```

## Step 7: Sync Code to myapp/

uWSGI reads code from `myapp/`, so sync it:

```bash
rsync -av --delete \
  --exclude='.git' \
  --exclude='env' \
  --exclude='.venv' \
  --exclude='tmp' \
  --exclude='myapp' \
  --exclude='*.db' \
  --exclude='*.db-journal' \
  . myapp/
```

## Step 8: Start the App

```bash
./start
```

## Step 9: Verify It Works

Check if running:
```bash
ps aux | grep uwsgi
# Should see uwsgi processes
```

Check logs:
```bash
tail -20 /home/actimish/logs/apps/actimish/uwsgi.log
# Should show gunicorn/uwsgi startup messages
```

Test an endpoint:
```bash
curl https://a.mishari.net/api/v1/instance
# Should return JSON with instance info
```

If DNS isn't set up yet:
```bash
curl -H "Host: a.mishari.net" http://127.0.0.1:21784/api/v1/instance
```

## Step 10: Update Future Deployments

When you push changes to GitHub, pull and deploy with:

```bash
cd /home/actimish/apps/actimish

./stop

git pull origin main

source env/bin/activate
pip install --only-binary greenlet -r requirements.txt
deactivate

# Sync code to myapp/
rsync -av --delete \
  --exclude='.git' \
  --exclude='env' \
  --exclude='.venv' \
  --exclude='tmp' \
  --exclude='myapp' \
  --exclude='*.db' \
  . myapp/

./start
```

Or use the automated script:
```bash
./opalstack_deploy.sh
```

## Troubleshooting

### "fatal: not a git repository"
Run Step 2 again to initialize git.

### "myapp/wsgi.py: No such file or directory" (uWSGI error)
The sync didn't work. Check:
```bash
ls -la myapp/wsgi.py
# Should exist
```

If missing, re-run the rsync:
```bash
rm -rf myapp
rsync -av --exclude='.git' --exclude='env' --exclude='.venv' --exclude='tmp' . myapp/
touch myapp/wsgi.py  # Force uWSGI reload
```

### "ModuleNotFoundError" in logs
Dependencies aren't installed:
```bash
source env/bin/activate
pip install -r requirements.txt
deactivate
./stop
./start
```

### "secret_key.txt not found"
Run setup again:
```bash
source env/bin/activate
python setup.py
deactivate
./stop
./start
```

### uWSGI crashes immediately
Check full logs:
```bash
tail -50 /home/actimish/logs/apps/actimish/uwsgi.log
```

Common causes:
- Missing data files (run `python setup.py`)
- Import errors (run `pip install -r requirements.txt`)
- Port conflict (run `./kill` then `./start`)

## File Checklist

After setup, you should have:

```
/home/actimish/apps/actimish/
├── .git/                    # Git repository
├── env/                     # Python virtualenv (from Opalstack)
├── myapp/                   # Synced code (uWSGI reads from here)
├── data/                    # Created by setup.py
│   ├── actimish.db
│   ├── secret_key.txt
│   ├── password.txt
│   └── keys/
├── tmp/                     # Temp files
├── logs/                    # Opalstack logs directory
├── .env                     # Environment variables (optional)
├── requirements.txt
├── setup.py
├── wsgi.py
├── app.py
├── config.py
├── models.py
├── routes/
├── utils/
├── tests/
├── start                    # Control script (Opalstack)
├── stop                     # Control script (Opalstack)
├── kill                     # Control script (Opalstack)
├── uwsgi.ini               # uWSGI config (Opalstack)
└── opalstack_deploy.sh     # Deployment script
```
