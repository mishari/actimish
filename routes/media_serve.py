"""
Serve uploaded media files and static assets (avatar, header).
"""

import os
from flask import Blueprint, send_from_directory, send_file, abort
import config

media_serve_bp = Blueprint("media_serve", __name__)


@media_serve_bp.route("/media/<path:filepath>")
def serve_media(filepath):
    """Serve uploaded media files."""
    full_path = os.path.join(config.MEDIA_DIR, filepath)
    if not os.path.isfile(full_path):
        abort(404)
    directory = os.path.dirname(full_path)
    filename = os.path.basename(full_path)
    return send_from_directory(directory, filename)


@media_serve_bp.route("/avatar.png")
def serve_avatar():
    """Serve the user's avatar."""
    avatar_path = os.path.join(config.DATA_DIR, "avatar.png")
    if os.path.isfile(avatar_path):
        return send_file(avatar_path, mimetype="image/png")
    # Return a default placeholder
    return _default_avatar(), 200, {"Content-Type": "image/svg+xml"}


@media_serve_bp.route("/header.png")
def serve_header():
    """Serve the user's header image."""
    header_path = os.path.join(config.DATA_DIR, "header.png")
    if os.path.isfile(header_path):
        return send_file(header_path, mimetype="image/png")
    return _default_header(), 200, {"Content-Type": "image/svg+xml"}


def _default_avatar():
    return """<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120">
<rect width="120" height="120" fill="#2b90d9"/>
<text x="60" y="70" text-anchor="middle" fill="white" font-size="48" font-family="sans-serif">M</text>
</svg>"""


def _default_header():
    return """<svg xmlns="http://www.w3.org/2000/svg" width="600" height="200">
<rect width="600" height="200" fill="#1a1b2e"/>
</svg>"""
