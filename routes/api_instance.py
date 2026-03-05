"""
Mastodon API: Instance information endpoints.
"""

from flask import Blueprint, jsonify
import config
from models import Status, Follower

api_instance_bp = Blueprint("api_instance", __name__)


def _instance_v1():
    """Build V1 instance response."""
    base = f"https://{config.DOMAIN}"
    local_posts = Status.query.filter_by(remote=False, deleted_at=None).count()

    return {
        "uri": config.DOMAIN,
        "title": f"{config.DISPLAY_NAME}'s instance",
        "short_description": f"Single-user ActivityPub instance for @{config.USERNAME}",
        "description": f"Single-user ActivityPub server powered by {config.SOFTWARE_NAME}",
        "email": "",
        "version": f"4.2.0 (compatible; {config.SOFTWARE_NAME} {config.SOFTWARE_VERSION})",
        "urls": {
            "streaming_api": f"wss://{config.DOMAIN}",
        },
        "stats": {
            "user_count": 1,
            "status_count": local_posts,
            "domain_count": 0,
        },
        "thumbnail": None,
        "languages": ["en"],
        "registrations": False,
        "approval_required": False,
        "invites_enabled": False,
        "configuration": {
            "accounts": {"max_featured_tags": 10},
            "statuses": {
                "max_characters": config.MAX_STATUS_LENGTH if config.MAX_STATUS_LENGTH > 0 else 500000,
                "max_media_attachments": config.MAX_MEDIA_ATTACHMENTS,
                "characters_reserved_per_url": 23,
            },
            "media_attachments": {
                "supported_mime_types": sorted(
                    list(config.ALLOWED_IMAGE_TYPES | config.ALLOWED_VIDEO_TYPES)
                ),
                "image_size_limit": config.MAX_IMAGE_SIZE,
                "image_matrix_limit": 16777216,
                "video_size_limit": config.MAX_VIDEO_SIZE,
                "video_frame_rate_limit": 60,
                "video_matrix_limit": 2304000,
            },
            "polls": {
                "max_options": 4,
                "max_characters_per_option": 50,
                "min_expiration": 300,
                "max_expiration": 2629746,
            },
        },
        "contact_account": None,
        "rules": [],
    }


@api_instance_bp.route("/api/v1/instance", methods=["GET"])
def instance_v1():
    return jsonify(_instance_v1())


@api_instance_bp.route("/api/v2/instance", methods=["GET"])
def instance_v2():
    base = f"https://{config.DOMAIN}"
    v1 = _instance_v1()
    return jsonify(
        {
            "domain": config.DOMAIN,
            "title": v1["title"],
            "version": v1["version"],
            "source_url": "https://github.com/mishari/actimish",
            "description": v1["description"],
            "usage": {
                "users": {"active_month": 1},
            },
            "thumbnail": None,
            "languages": ["en"],
            "configuration": v1["configuration"],
            "registrations": {
                "enabled": False,
                "approval_required": False,
                "message": None,
                "url": None,
            },
            "contact": {
                "email": "",
                "account": None,
            },
            "rules": [],
            "api_versions": {
                "mastodon": 2,
            },
        }
    )


@api_instance_bp.route("/api/v1/instance/rules", methods=["GET"])
def instance_rules():
    return jsonify([])


@api_instance_bp.route("/api/v1/instance/peers", methods=["GET"])
def instance_peers():
    return jsonify([])


@api_instance_bp.route("/api/v1/custom_emojis", methods=["GET"])
def custom_emojis():
    return jsonify([])


@api_instance_bp.route("/api/v1/announcements", methods=["GET"])
def announcements():
    return jsonify([])
