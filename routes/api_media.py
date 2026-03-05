"""
Mastodon API: Media upload endpoints.
"""

import os
import uuid
import time

from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename

import config
from models import db, MediaAttachment
from utils.auth import require_auth
from utils.serializers import serialize_media

api_media_bp = Blueprint("api_media", __name__)


def _process_upload(file_obj):
    """
    Save an uploaded file and create a MediaAttachment record.
    Returns the MediaAttachment or (error_message, status_code).
    """
    if not file_obj or not file_obj.filename:
        return "No file provided", 422

    # Detect MIME type from content
    file_obj.seek(0)
    header_bytes = file_obj.read(2048)
    file_obj.seek(0)

    mime_type = _detect_mime(header_bytes, file_obj.filename)
    if not mime_type:
        return "Could not determine file type", 422

    # Determine media type
    if mime_type in config.ALLOWED_IMAGE_TYPES:
        media_type = "image"
        max_size = config.MAX_IMAGE_SIZE
    elif mime_type in config.ALLOWED_VIDEO_TYPES:
        media_type = "video"
        max_size = config.MAX_VIDEO_SIZE
    else:
        return f"Unsupported media type: {mime_type}", 422

    # Read entire file to check size
    file_obj.seek(0, 2)  # Seek to end
    file_size = file_obj.tell()
    file_obj.seek(0)

    if file_size > max_size:
        return f"File too large (max {max_size // (1024*1024)} MB)", 422

    # Generate unique filename
    ext = _extension_for_mime(mime_type)
    unique_name = f"{uuid.uuid4().hex}{ext}"
    # Organize by year/month
    now = time.localtime()
    subdir = f"{now.tm_year}/{now.tm_mon:02d}"
    media_dir = os.path.join(config.MEDIA_DIR, subdir)
    os.makedirs(media_dir, exist_ok=True)

    file_path = os.path.join(media_dir, unique_name)
    file_obj.save(file_path)

    # Get image dimensions if applicable
    width, height = None, None
    thumb_relative_path = None
    if media_type == "image":
        try:
            from PIL import Image
            with Image.open(file_path) as img:
                width, height = img.size

                thumb_name = f"{os.path.splitext(unique_name)[0]}_thumb{ext}"
                thumb_path = os.path.join(media_dir, thumb_name)
                thumb = img.copy()
                thumb.thumbnail((800, 800))
                try:
                    thumb.save(thumb_path)
                except Exception:
                    thumb.save(thumb_path, format="PNG")
                thumb_relative_path = f"{subdir}/{thumb_name}"
        except Exception:
            pass

    # Relative path for storage
    relative_path = f"{subdir}/{unique_name}"

    attachment = MediaAttachment(
        file_path=relative_path,
        thumbnail_path=thumb_relative_path,
        media_type=media_type,
        mime_type=mime_type,
        size=file_size,
        width=width,
        height=height,
        processing=False,
    )
    db.session.add(attachment)
    db.session.commit()

    return attachment


def _detect_mime(header_bytes, filename):
    """Detect MIME type from file header bytes, falling back to extension."""
    # Magic bytes detection
    if header_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if header_bytes[:2] == b"\xff\xd8":
        return "image/jpeg"
    if header_bytes[:4] == b"GIF8":
        return "image/gif"
    if header_bytes[:4] == b"RIFF" and header_bytes[8:12] == b"WEBP":
        return "image/webp"
    if header_bytes[4:8] == b"ftyp":
        return "video/mp4"
    if header_bytes[:4] == b"\x1a\x45\xdf\xa3":
        return "video/webm"

    # Fall back to extension
    ext = os.path.splitext(filename)[1].lower()
    ext_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".mov": "video/quicktime",
    }
    return ext_map.get(ext)


def _extension_for_mime(mime_type):
    """Get file extension for a MIME type."""
    mime_map = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "video/mp4": ".mp4",
        "video/webm": ".webm",
        "video/quicktime": ".mov",
    }
    return mime_map.get(mime_type, ".bin")


@api_media_bp.route("/api/v2/media", methods=["POST"])
@require_auth
def upload_media_v2():
    """Upload media (async-style, but we process synchronously for simplicity)."""
    file_obj = request.files.get("file")
    result = _process_upload(file_obj)

    if isinstance(result, tuple):
        return jsonify({"error": result[0]}), result[1]
    if isinstance(result, str):
        return jsonify({"error": result}), 422

    attachment = result

    # Handle optional metadata
    description = request.form.get("description", "")
    focus = request.form.get("focus", "")
    if description:
        attachment.description = description
    if focus:
        try:
            parts = focus.split(",")
            attachment.focus_x = float(parts[0])
            attachment.focus_y = float(parts[1])
        except (ValueError, IndexError):
            pass
    db.session.commit()

    return jsonify(serialize_media(attachment)), 200


@api_media_bp.route("/api/v1/media", methods=["POST"])
@require_auth
def upload_media_v1():
    """Upload media (synchronous, deprecated but used by some clients)."""
    file_obj = request.files.get("file")
    result = _process_upload(file_obj)

    if isinstance(result, tuple):
        return jsonify({"error": result[0]}), result[1]
    if isinstance(result, str):
        return jsonify({"error": result}), 422

    attachment = result

    description = request.form.get("description", "")
    focus = request.form.get("focus", "")
    if description:
        attachment.description = description
    if focus:
        try:
            parts = focus.split(",")
            attachment.focus_x = float(parts[0])
            attachment.focus_y = float(parts[1])
        except (ValueError, IndexError):
            pass
    db.session.commit()

    return jsonify(serialize_media(attachment)), 200


@api_media_bp.route("/api/v1/media/<int:media_id>", methods=["GET"])
@require_auth
def get_media(media_id):
    """Check media processing status."""
    attachment = MediaAttachment.query.get(media_id)
    if not attachment:
        return jsonify({"error": "Record not found"}), 404

    if attachment.processing:
        return jsonify(serialize_media(attachment)), 206  # Partial Content = still processing

    return jsonify(serialize_media(attachment)), 200


@api_media_bp.route("/api/v1/media/<int:media_id>", methods=["PUT"])
@require_auth
def update_media(media_id):
    """Update media metadata before posting."""
    attachment = MediaAttachment.query.get(media_id)
    if not attachment:
        return jsonify({"error": "Record not found"}), 404

    data = request.get_json(silent=True) or request.form.to_dict()

    if "description" in data:
        attachment.description = data["description"]
    if "focus" in data:
        focus = data["focus"]
        try:
            if isinstance(focus, str):
                parts = focus.split(",")
                attachment.focus_x = float(parts[0])
                attachment.focus_y = float(parts[1])
        except (ValueError, IndexError):
            pass

    db.session.commit()
    return jsonify(serialize_media(attachment))
