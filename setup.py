#!/usr/bin/env python3
"""
Actimish setup script.
Run this once to initialize the database, generate keys, and set a password.
"""

import os
import sys
import secrets


def main():
    # Ensure we're in the right directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)
    sys.path.insert(0, base_dir)

    import config

    print(f"Setting up Actimish for {config.USERNAME}@{config.DOMAIN}")
    print()

    # Create directories
    os.makedirs(config.DATA_DIR, exist_ok=True)
    os.makedirs(config.MEDIA_DIR, exist_ok=True)
    os.makedirs(config.KEYS_DIR, exist_ok=True)
    print(f"  Created data directories at {config.DATA_DIR}")

    # Set password
    pw_file = os.path.join(config.DATA_DIR, "password.txt")
    if not os.path.exists(pw_file):
        password = input("Set your login password (used to authorize apps like Tusky): ").strip()
        if not password:
            password = secrets.token_urlsafe(16)
            print(f"  Generated random password: {password}")
        with open(pw_file, "w") as f:
            f.write(password)
        os.chmod(pw_file, 0o600)
        print(f"  Password saved to {pw_file}")
    else:
        print(f"  Password file already exists at {pw_file}")

    # Generate secret key
    secret_file = os.path.join(config.DATA_DIR, "secret_key.txt")
    if not os.path.exists(secret_file):
        secret = secrets.token_hex(32)
        with open(secret_file, "w") as f:
            f.write(secret)
        os.chmod(secret_file, 0o600)
        print(f"  Generated Flask secret key")
    else:
        print(f"  Secret key already exists")

    # Initialize database and keys
    from app import create_app
    app = create_app()
    with app.app_context():
        from models import db
        db.create_all()
        print(f"  Database initialized at {config.DB_PATH}")

    print()
    print("Setup complete!")
    print()
    print("Next steps:")
    print(f"  1. Point your domain {config.DOMAIN} to this server")
    print(f"  2. Set environment variables (or edit config.py):")
    print(f"     export ACTIMISH_DOMAIN={config.DOMAIN}")
    print(f"     export ACTIMISH_PASSWORD=<your-password>")
    print(f"     export ACTIMISH_SECRET_KEY=$(cat {secret_file})")
    print(f"  3. On Opalstack, configure your WSGI app to use wsgi.py")
    print(f"  4. Install dependencies: pip install -r requirements.txt")
    print(f"  5. Open Tusky and log in to https://{config.DOMAIN}")
    print()


if __name__ == "__main__":
    main()
