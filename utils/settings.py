"""
Settings persistence for local user profile (display_name, bio, avatar/header metadata).
Stores to data/settings.json so values survive server restart.
"""
import os
import json
import tempfile
from config import DATA_DIR


SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")

# Default settings shape
DEFAULT_SETTINGS = {
    "display_name": None,
    "bio": None,
    "avatar_mime": None,
    "header_mime": None,
}


def load_settings():
    """
    Load settings from data/settings.json.
    Returns dict with default values for missing keys.
    """
    if not os.path.exists(SETTINGS_FILE):
        return DEFAULT_SETTINGS.copy()

    try:
        with open(SETTINGS_FILE, "r") as f:
            data = json.load(f)
        # Merge with defaults (in case file is missing keys)
        result = DEFAULT_SETTINGS.copy()
        result.update(data)
        return result
    except (json.JSONDecodeError, IOError):
        return DEFAULT_SETTINGS.copy()


def save_settings(data):
    """
    Save settings to data/settings.json atomically.
    Writes to a temp file first, then renames to avoid corruption.
    """
    os.makedirs(DATA_DIR, exist_ok=True)

    # Write to temp file first
    fd, temp_path = tempfile.mkstemp(dir=DATA_DIR, suffix=".json")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        # Atomic rename
        os.replace(temp_path, SETTINGS_FILE)
    except Exception:
        # Clean up temp file on error
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


def get_setting(key, default=None):
    """
    Get a single setting value.
    Returns default if key not found or is None.
    """
    settings = load_settings()
    value = settings.get(key)
    return value if value is not None else default


def update_settings(**kwargs):
    """
    Update multiple settings at once.
    Only updates keys provided; others are left as-is.
    """
    settings = load_settings()
    settings.update(kwargs)
    save_settings(settings)
