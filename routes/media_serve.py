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


@media_serve_bp.route("/avatar.<ext>", methods=["GET"])
@media_serve_bp.route("/avatar.png", methods=["GET"])
def serve_avatar(ext=None):
    """Serve the user's avatar with correct MIME type."""
    from utils.settings import get_setting
    
    # Try to find avatar with any extension
    avatar_path = None
    mime_type = "image/png"
    
    for check_ext in ["png", "jpg", "jpeg", "gif", "webp"]:
        check_path = os.path.join(config.DATA_DIR, f"avatar.{check_ext}")
        if os.path.isfile(check_path):
            avatar_path = check_path
            # Get MIME type from settings or detect from extension
            avatar_mime = get_setting("avatar_mime")
            if avatar_mime:
                mime_type = avatar_mime
            else:
                ext_mime_map = {
                    "png": "image/png",
                    "jpg": "image/jpeg",
                    "jpeg": "image/jpeg",
                    "gif": "image/gif",
                    "webp": "image/webp",
                }
                mime_type = ext_mime_map.get(check_ext, "image/png")
            break
    
    if avatar_path:
        return send_file(avatar_path, mimetype=mime_type)
    
    # Return a default placeholder
    return _default_avatar(), 200, {"Content-Type": "image/svg+xml"}


@media_serve_bp.route("/header.<ext>", methods=["GET"])
@media_serve_bp.route("/header.png", methods=["GET"])
def serve_header(ext=None):
    """Serve the user's header image with correct MIME type."""
    from utils.settings import get_setting
    
    # Try to find header with any extension
    header_path = None
    mime_type = "image/png"
    
    for check_ext in ["png", "jpg", "jpeg", "gif", "webp"]:
        check_path = os.path.join(config.DATA_DIR, f"header.{check_ext}")
        if os.path.isfile(check_path):
            header_path = check_path
            # Get MIME type from settings or detect from extension
            header_mime = get_setting("header_mime")
            if header_mime:
                mime_type = header_mime
            else:
                ext_mime_map = {
                    "png": "image/png",
                    "jpg": "image/jpeg",
                    "jpeg": "image/jpeg",
                    "gif": "image/gif",
                    "webp": "image/webp",
                }
                mime_type = ext_mime_map.get(check_ext, "image/png")
            break
    
    if header_path:
        return send_file(header_path, mimetype=mime_type)
    
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
