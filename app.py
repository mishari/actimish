"""
Flask application factory for Actimish.
"""

import os
import logging
from flask import Flask, jsonify
from models import db
import config

logging.basicConfig(level=logging.INFO)


def create_app():
    app = Flask(__name__)
    app.config.from_object(config)

    # Ensure data directories exist
    os.makedirs(config.DATA_DIR, exist_ok=True)
    os.makedirs(config.MEDIA_DIR, exist_ok=True)
    os.makedirs(config.KEYS_DIR, exist_ok=True)

    # Init database
    db.init_app(app)

    with app.app_context():
        db.create_all()
        # Generate RSA keypair if not present
        from utils.crypto import ensure_keypair
        ensure_keypair()

    # ── CORS: allow Tusky and other clients ───────────────────────
    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = (
            "Authorization, Content-Type, Idempotency-Key"
        )
        response.headers["Access-Control-Allow-Methods"] = (
            "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        )
        response.headers["Access-Control-Expose-Headers"] = "Link"
        return response

    @app.before_request
    def handle_preflight():
        from flask import request
        if request.method == "OPTIONS":
            return "", 204

    # ── Error handlers ────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Record not found"}), 404

    @app.errorhandler(413)
    def too_large(e):
        return jsonify({"error": "File too large"}), 413

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({"error": "Internal server error"}), 500

    # Register blueprints
    from routes.wellknown import wellknown_bp
    from routes.activitypub import activitypub_bp
    from routes.oauth import oauth_bp
    from routes.api_instance import api_instance_bp
    from routes.api_accounts import api_accounts_bp
    from routes.api_statuses import api_statuses_bp
    from routes.api_timelines import api_timelines_bp
    from routes.api_media import api_media_bp
    from routes.api_notifications import api_notifications_bp
    from routes.api_search import api_search_bp
    from routes.api_misc import api_misc_bp

    app.register_blueprint(wellknown_bp)
    app.register_blueprint(activitypub_bp)
    app.register_blueprint(oauth_bp)
    app.register_blueprint(api_instance_bp)
    app.register_blueprint(api_accounts_bp)
    app.register_blueprint(api_statuses_bp)
    app.register_blueprint(api_timelines_bp)
    app.register_blueprint(api_media_bp)
    app.register_blueprint(api_notifications_bp)
    app.register_blueprint(api_search_bp)
    app.register_blueprint(api_misc_bp)

    # Serve uploaded media files
    from routes.media_serve import media_serve_bp
    app.register_blueprint(media_serve_bp)

    return app
