"""
OAuth2 endpoints for Mastodon API compatibility.

Since this is a single-user server, the OAuth flow is simplified:
- App registration works normally
- Authorization shows a simple form with a password
- Token exchange works normally
"""

import secrets
import time

from flask import Blueprint, request, jsonify, redirect, render_template_string
import config
from models import db, OAuthApp, OAuthToken, OAuthAuthCode

oauth_bp = Blueprint("oauth", __name__)

# Simple HTML template for the authorization page
AUTH_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <title>Authorize {{ app_name }}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: system-ui, sans-serif; max-width: 420px; margin: 60px auto; padding: 20px; }
        h1 { font-size: 1.4em; }
        .app-name { color: #2b90d9; }
        input[type=password] { width: 100%; padding: 10px; margin: 10px 0; box-sizing: border-box; }
        button { background: #2b90d9; color: white; border: none; padding: 12px 24px;
                 cursor: pointer; font-size: 1em; border-radius: 4px; width: 100%; }
        button:hover { background: #1a7bc4; }
        .scopes { color: #666; font-size: 0.9em; margin: 10px 0; }
    </style>
</head>
<body>
    <h1>Authorize <span class="app-name">{{ app_name }}</span></h1>
    <p class="scopes">Requested permissions: {{ scope }}</p>
    <form method="POST">
        <input type="hidden" name="client_id" value="{{ client_id }}">
        <input type="hidden" name="redirect_uri" value="{{ redirect_uri }}">
        <input type="hidden" name="scope" value="{{ scope }}">
        <input type="hidden" name="state" value="{{ state }}">
        <input type="hidden" name="response_type" value="code">
        <label for="password">Enter your password:</label>
        <input type="password" name="password" id="password" required autofocus>
        <button type="submit">Authorize</button>
    </form>
</body>
</html>"""


@oauth_bp.route("/api/v1/apps", methods=["POST"])
def register_app():
    """Register a new OAuth application."""
    data = request.get_json(silent=True) or {}
    if not data:
        data = request.form.to_dict()

    client_name = data.get("client_name", "Unknown")
    redirect_uris = data.get("redirect_uris", "urn:ietf:wg:oauth:2.0:oob")
    scopes = data.get("scopes", "read")
    website = data.get("website")

    # Handle redirect_uris as list or string
    if isinstance(redirect_uris, list):
        redirect_uris_str = " ".join(redirect_uris)
    else:
        redirect_uris_str = redirect_uris

    app_obj = OAuthApp(
        client_id=secrets.token_hex(32),
        client_secret=secrets.token_hex(32),
        client_name=client_name,
        redirect_uris=redirect_uris_str,
        scopes=scopes,
        website=website,
    )
    db.session.add(app_obj)
    db.session.commit()

    # Return all redirect URIs as an array
    uris_list = redirect_uris_str.split()

    return jsonify(
        {
            "id": str(app_obj.id),
            "name": app_obj.client_name,
            "client_id": app_obj.client_id,
            "client_secret": app_obj.client_secret,
            "client_secret_expires_at": 0,
            "redirect_uri": uris_list[0] if uris_list else redirect_uris_str,
            "redirect_uris": uris_list,
            "scopes": scopes.split() if isinstance(scopes, str) else scopes,
            "website": website,
        }
    )


@oauth_bp.route("/oauth/authorize", methods=["GET"])
def authorize_get():
    """Show the authorization form."""
    client_id = request.args.get("client_id", "")
    redirect_uri = request.args.get("redirect_uri", "")
    scope = request.args.get("scope", "read")
    state = request.args.get("state", "")

    app_obj = OAuthApp.query.filter_by(client_id=client_id).first()
    if not app_obj:
        return jsonify({"error": "Invalid client_id"}), 400

    return render_template_string(
        AUTH_TEMPLATE,
        app_name=app_obj.client_name,
        client_id=client_id,
        redirect_uri=redirect_uri,
        scope=scope,
        state=state,
    )


@oauth_bp.route("/oauth/authorize", methods=["POST"])
def authorize_post():
    """Process authorization: verify password, issue auth code."""
    client_id = request.form.get("client_id", "")
    redirect_uri = request.form.get("redirect_uri", "")
    scope = request.form.get("scope", "read")
    state = request.form.get("state", "")
    password = request.form.get("password", "")

    app_obj = OAuthApp.query.filter_by(client_id=client_id).first()
    if not app_obj:
        return jsonify({"error": "Invalid client_id"}), 400

    # Verify password
    import os
    expected_password = os.environ.get("ACTIMISH_PASSWORD", "")
    if not expected_password:
        # Read from file as fallback
        pw_file = os.path.join(config.DATA_DIR, "password.txt")
        if os.path.exists(pw_file):
            with open(pw_file, "r") as f:
                expected_password = f.read().strip()

    if not expected_password or password != expected_password:
        return render_template_string(
            AUTH_TEMPLATE + '<p style="color:red">Invalid password</p>',
            app_name=app_obj.client_name,
            client_id=client_id,
            redirect_uri=redirect_uri,
            scope=scope,
            state=state,
        )

    # Issue auth code
    code = secrets.token_hex(32)
    auth_code = OAuthAuthCode(
        code=code,
        app_id=app_obj.id,
        redirect_uri=redirect_uri,
        scope=scope,
    )
    db.session.add(auth_code)
    db.session.commit()

    # Redirect with code
    sep = "&" if "?" in redirect_uri else "?"
    url = f"{redirect_uri}{sep}code={code}"
    if state:
        url += f"&state={state}"

    return redirect(url)


@oauth_bp.route("/oauth/token", methods=["POST"])
def token():
    """Exchange authorization code for access token."""
    data = request.get_json(silent=True) or {}
    if not data:
        data = request.form.to_dict()

    grant_type = data.get("grant_type", "")
    client_id = data.get("client_id", "")
    client_secret = data.get("client_secret", "")
    code = data.get("code", "")
    redirect_uri = data.get("redirect_uri", "")

    if grant_type == "authorization_code":
        app_obj = OAuthApp.query.filter_by(
            client_id=client_id, client_secret=client_secret
        ).first()
        if not app_obj:
            return jsonify({"error": "Invalid client credentials"}), 401

        auth_code = OAuthAuthCode.query.filter_by(
            code=code, app_id=app_obj.id, used=False
        ).first()
        if not auth_code:
            return jsonify({"error": "Invalid authorization code"}), 400

        # Check code is not too old (10 minutes)
        if int(time.time()) - auth_code.created_at > 600:
            return jsonify({"error": "Authorization code expired"}), 400

        auth_code.used = True

        access_token = secrets.token_hex(32)
        token_obj = OAuthToken(
            access_token=access_token,
            scope=auth_code.scope,
            app_id=app_obj.id,
        )
        db.session.add(token_obj)
        db.session.commit()

        return jsonify(
            {
                "access_token": access_token,
                "token_type": "Bearer",
                "scope": auth_code.scope,
                "created_at": token_obj.created_at,
            }
        )

    elif grant_type == "client_credentials":
        # App-level token (used by some clients for pre-auth calls)
        app_obj = OAuthApp.query.filter_by(
            client_id=client_id, client_secret=client_secret
        ).first()
        if not app_obj:
            return jsonify({"error": "Invalid client credentials"}), 401

        access_token = secrets.token_hex(32)
        token_obj = OAuthToken(
            access_token=access_token,
            scope="read",
            app_id=app_obj.id,
        )
        db.session.add(token_obj)
        db.session.commit()

        return jsonify(
            {
                "access_token": access_token,
                "token_type": "Bearer",
                "scope": "read",
                "created_at": token_obj.created_at,
            }
        )

    return jsonify({"error": "Unsupported grant_type"}), 400


@oauth_bp.route("/oauth/revoke", methods=["POST"])
def revoke():
    """Revoke an access token."""
    data = request.get_json(silent=True) or {}
    if not data:
        data = request.form.to_dict()

    token_str = data.get("token", "")
    token_obj = OAuthToken.query.filter_by(access_token=token_str).first()
    if token_obj:
        token_obj.revoked = True
        db.session.commit()

    return jsonify({}), 200


@oauth_bp.route("/api/v1/apps/verify_credentials", methods=["GET"])
def verify_app():
    """Verify that the app token is valid."""
    from utils.auth import require_auth

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return jsonify({"error": "The access token is invalid"}), 401
    token_str = auth[7:]
    token_obj = OAuthToken.query.filter_by(
        access_token=token_str, revoked=False
    ).first()
    if not token_obj:
        return jsonify({"error": "The access token is invalid"}), 401

    app_obj = token_obj.app
    return jsonify(
        {
            "name": app_obj.client_name,
            "website": app_obj.website,
        }
    )
