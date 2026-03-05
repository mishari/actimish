# AGENTS

This file is instructions for agentic coding assistants working in this repo.

- Cursor rules: none found in `.cursor/rules/` or `.cursorrules`
- Copilot rules: none found in `.github/copilot-instructions.md`

## Project Overview

Actimish is a small Flask-based, single-user ActivityPub server with a
Mastodon-compatible API surface.

## Repo Map

- App factory: `app.py:create_app()`
- WSGI entrypoint: `wsgi.py:application`
- One-time setup: `setup.py` (creates `data/`, DB, keys, password/secret files)
- Deployment helper: `opalstack_start.sh` (gunicorn + env loading)
- Config: `config.py` (env-driven, paths under `data/`)
- DB models: `models.py` (Flask-SQLAlchemy / SQLite)
- Routes: `routes/*.py` (Flask blueprints)
- Helpers: `utils/*.py` (auth, federation, crypto, serializers)
- Work tracking: `TODO.md`

## Build / Run / Lint / Test

### Install (Build)

Create a virtualenv and install requirements:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### One-Time Local Setup

Initializes DB + generates keys + stores password/secret files under `data/`:

```bash
python setup.py
```

### Run (Dev)

```bash
python wsgi.py
```

### Run (Prod-like)

Gunicorn:

```bash
gunicorn wsgi:application \
  --bind 127.0.0.1:8000 \
  --workers 2 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
```

Opalstack helper:

```bash
./opalstack_start.sh
```

### Lint / Format

- No linting/formatting tooling is configured in this repo.
- Do not introduce or run auto-formatters unless explicitly requested.
- When editing, keep changes minimal and match the style in the touched file.

### Tests

- Tests live under `tests/` and use stdlib `unittest`.
- Run all tests:

```bash
python -m unittest -v
```

- Run a single test:

```bash
python -m unittest -v tests.test_media_upload.TestMediaUpload.test_upload_png_image
```

- TDD: add a failing test first (red), implement (green), then refactor.

## Config / Secrets / Data

Primary env vars (see `config.py`, `setup.py`, `opalstack_start.sh`):

- `ACTIMISH_DOMAIN`
- `ACTIMISH_USERNAME`
- `ACTIMISH_DISPLAY_NAME`
- `ACTIMISH_BIO`
- `ACTIMISH_DATA_DIR` (defaults to `./data`)
- `ACTIMISH_SECRET_KEY` (or `data/secret_key.txt`)
- `ACTIMISH_PASSWORD` (or `data/password.txt`)

Never commit these (gitignored):

- `.env`, `data/`, `*.db`, `*.pem`, `venv/`, `.venv/`

Security rules:

- Never log secrets (password, secret key, OAuth token values, private keys).
- Keep file writes limited to `config.DATA_DIR`, `config.MEDIA_DIR`,
  `config.KEYS_DIR`.
- Avoid weakening auth or signature verification without a clear reason.

## Code Style Guidelines (Match Existing Code)

### Imports

- Order imports: (1) stdlib, (2) third-party, (3) local (`config`, `models`,
  `utils`).
- Prefer explicit imports; avoid `import *`.
- Local imports inside a function are OK when needed to break import cycles or
  keep optional/slow imports off hot paths.

### Formatting

- 4 spaces indentation; no tabs.
- Keep changes localized; do not reformat unrelated blocks.
- This repo is hand-formatted; preserve existing patterns.

### Naming

- Files/modules: `snake_case.py`
- Functions/variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Internal helpers: prefix `_` (e.g. `_handle_follow`, `_paginate_statuses`).
- Blueprints:
  - variable name: `*_bp` (e.g. `api_statuses_bp`)
  - blueprint name: short, stable string (e.g. `"api_statuses"`)

### Types

- Type hints are minimal today; add them only when they reduce ambiguity.
- Good targets: pure helpers in `utils/`, serializer helpers, non-obvious
  return types.
- Do not add typing-only runtime dependencies.

### Flask / API Patterns

- Input parsing:
  - Prefer JSON: `request.get_json(silent=True) or {}`
  - Fallback to forms: `request.form.to_dict()` (use `flat=False` if arrays)
- Outputs:
  - Errors: `return jsonify({"error": "..."}), <status_code>`
  - Success: `return jsonify(payload), 200` (or endpoint-appropriate code)
- Auth:
  - Use `@require_auth` and `@optional_auth` from `utils/auth.py`.
  - `require_auth` attaches `request.oauth_token`; treat it as per-request
    state.
- Pagination:
  - Use Mastodon-style `Link` header patterns already used in `routes/`.

### Database / SQLAlchemy

- SQLite DB lives under `config.DATA_DIR` (see `config.DB_PATH`).
- Prefer one logical commit per request.
- Use `db.session.flush()` when you need IDs before commit.
- Validate IDs from request input:
  - wrap `int(...)` in `try/except (ValueError, TypeError)`.

### Error Handling & Logging

- Prefer consistent JSON errors (existing examples):
  - 404: `{"error": "Record not found"}`
  - auth: `{"error": "The access token is invalid"}`
- Network/federation:
  - Always set timeouts.
  - Log failures; return safe fallbacks instead of crashing.
- Avoid broad `except Exception` unless best-effort is intended; if used, log.

### API Compatibility Constraints

- Many endpoints aim for Mastodon client compatibility.
- Keep response shapes stable; see `utils/serializers.py`.

## Adding New Code (Local Conventions)

- New blueprint:
  - add `routes/<feature>.py` with `<feature>_bp`
  - register it in `app.py` alongside existing blueprints
- New model:
  - add to `models.py`; DB is created via `db.create_all()` in `create_app()`
    and `setup.py`
- New dependency:
  - add to `requirements.txt` using the existing pin style

## Quick Sanity Checks

```bash
python3 -m compileall .
python wsgi.py
```

Manual smoke endpoints to hit:

- `/.well-known/webfinger`
- `/api/v1/instance`
- `/api/v1/timelines/public`
