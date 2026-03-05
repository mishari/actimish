"""
Actimish configuration.
Edit this file to match your deployment environment.
"""

import os
import secrets

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Domain & Identity ──────────────────────────────────────────────
DOMAIN = os.environ.get("ACTIMISH_DOMAIN", "a.mishari.net")
USERNAME = os.environ.get("ACTIMISH_USERNAME", "mishari")

# Display name and bio can be overridden by persisted settings
_DISPLAY_NAME_ENV = os.environ.get("ACTIMISH_DISPLAY_NAME", "Mishari")
_BIO_ENV = os.environ.get("ACTIMISH_BIO", "")
DISPLAY_NAME = _DISPLAY_NAME_ENV
BIO = _BIO_ENV


def apply_persisted_settings():
    """
    Load persisted display_name and bio from data/settings.json.
    Called on app startup to apply any changes made via update_credentials.
    """
    global DISPLAY_NAME, BIO
    try:
        from utils.settings import get_setting
        display_name = get_setting("display_name")
        bio = get_setting("bio")
        if display_name is not None:
            DISPLAY_NAME = display_name
        if bio is not None:
            BIO = bio
    except (ImportError, FileNotFoundError):
        # Settings file doesn't exist yet or error reading it
        pass

# ── Paths ──────────────────────────────────────────────────────────
DATA_DIR = os.environ.get("ACTIMISH_DATA_DIR", os.path.join(BASE_DIR, "data"))
DB_PATH = os.path.join(DATA_DIR, "actimish.db")
MEDIA_DIR = os.path.join(DATA_DIR, "media")
KEYS_DIR = os.path.join(DATA_DIR, "keys")

# ── Flask / Security ──────────────────────────────────────────────
def _load_secret_key():
    """Load secret key from env, file, or generate a new one."""
    key = os.environ.get("ACTIMISH_SECRET_KEY")
    if key:
        return key
    key_file = os.path.join(DATA_DIR, "secret_key.txt")
    if os.path.exists(key_file):
        with open(key_file, "r") as f:
            return f.read().strip()
    return secrets.token_hex(32)

SECRET_KEY = _load_secret_key()
SQLALCHEMY_DATABASE_URI = f"sqlite:///{DB_PATH}"
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Allow large request bodies for media uploads
MAX_CONTENT_LENGTH = 120 * 1024 * 1024  # 120 MB

# ── Media limits ──────────────────────────────────────────────────
MAX_IMAGE_SIZE = 10 * 1024 * 1024       # 10 MB
MAX_VIDEO_SIZE = 100 * 1024 * 1024      # 100 MB
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/webm", "video/quicktime"}

# ── Status limits ─────────────────────────────────────────────────
MAX_STATUS_LENGTH = 0  # 0 = unlimited
MAX_MEDIA_ATTACHMENTS = 4

# ── Software identity (reported via nodeinfo / instance API) ──────
SOFTWARE_NAME = "actimish"
SOFTWARE_VERSION = "0.1.0"
