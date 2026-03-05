"""
Authentication helpers for the Mastodon-compatible API.
"""

from functools import wraps
from flask import request, jsonify
from models import db, OAuthToken


def require_auth(f):
    """Decorator: require a valid Bearer token."""

    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "The access token is invalid"}), 401
        token_str = auth[7:]
        token = OAuthToken.query.filter_by(
            access_token=token_str, revoked=False
        ).first()
        if not token:
            return jsonify({"error": "The access token is invalid"}), 401
        request.oauth_token = token
        return f(*args, **kwargs)

    return decorated


def optional_auth(f):
    """Decorator: attach token info if present, but don't require it."""

    @wraps(f)
    def decorated(*args, **kwargs):
        request.oauth_token = None
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token_str = auth[7:]
            token = OAuthToken.query.filter_by(
                access_token=token_str, revoked=False
            ).first()
            if token:
                request.oauth_token = token
        return f(*args, **kwargs)

    return decorated
