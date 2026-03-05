"""
Mastodon API: Miscellaneous endpoints (markers, lists, filters, suggestions, etc.).
"""

import time

from flask import Blueprint, request, jsonify
from models import db, Marker, Favourite, Bookmark, Status
from utils.auth import require_auth
from utils.serializers import serialize_status

api_misc_bp = Blueprint("api_misc", __name__)


# ── Markers ───────────────────────────────────────────────────────


@api_misc_bp.route("/api/v1/markers", methods=["GET"])
@require_auth
def get_markers():
    timelines = request.args.getlist("timeline[]") or request.args.getlist("timeline")
    result = {}
    for tl in timelines:
        marker = Marker.query.filter_by(timeline=tl).first()
        if marker:
            from utils.serializers import _epoch_to_iso

            result[tl] = {
                "last_read_id": marker.last_read_id,
                "version": marker.version,
                "updated_at": _epoch_to_iso(marker.updated_at),
            }
    return jsonify(result)


@api_misc_bp.route("/api/v1/markers", methods=["POST"])
@require_auth
def save_markers():
    data = request.get_json(silent=True) or request.form.to_dict()
    result = {}
    for tl in ("home", "notifications"):
        if tl in data and isinstance(data[tl], dict):
            last_read_id = data[tl].get("last_read_id")
            if last_read_id:
                marker = Marker.query.filter_by(timeline=tl).first()
                if marker:
                    marker.last_read_id = str(last_read_id)
                    marker.version += 1
                else:
                    marker = Marker(
                        timeline=tl,
                        last_read_id=str(last_read_id),
                        version=0,
                    )
                    db.session.add(marker)
                db.session.commit()
                from utils.serializers import _epoch_to_iso

                result[tl] = {
                    "last_read_id": marker.last_read_id,
                    "version": marker.version,
                    "updated_at": _epoch_to_iso(marker.updated_at),
                }
    return jsonify(result)


# ── Favourites & Bookmarks listing ───────────────────────────────


@api_misc_bp.route("/api/v1/favourites", methods=["GET"])
@require_auth
def list_favourites():
    limit = min(int(request.args.get("limit", 20)), 40)
    max_id = request.args.get("max_id")

    query = Favourite.query.filter_by(local=True)
    if max_id:
        query = query.filter(Favourite.id < int(max_id))

    favs = query.order_by(Favourite.id.desc()).limit(limit).all()
    result = []
    for f in favs:
        if f.status and not f.status.deleted_at:
            result.append(serialize_status(f.status, for_account="local"))
    return jsonify(result)


@api_misc_bp.route("/api/v1/bookmarks", methods=["GET"])
@require_auth
def list_bookmarks():
    limit = min(int(request.args.get("limit", 20)), 40)
    max_id = request.args.get("max_id")

    query = Bookmark.query
    if max_id:
        query = query.filter(Bookmark.id < int(max_id))

    bookmarks = query.order_by(Bookmark.id.desc()).limit(limit).all()
    result = []
    for b in bookmarks:
        if b.status and not b.status.deleted_at:
            result.append(serialize_status(b.status, for_account="local"))
    return jsonify(result)


# ── Lists (stub) ─────────────────────────────────────────────────


@api_misc_bp.route("/api/v1/lists", methods=["GET"])
@require_auth
def list_lists():
    return jsonify([])


@api_misc_bp.route("/api/v1/lists", methods=["POST"])
@require_auth
def create_list():
    data = request.get_json(silent=True) or request.form.to_dict()
    return jsonify(
        {
            "id": "1",
            "title": data.get("title", ""),
            "replies_policy": data.get("replies_policy", "list"),
            "exclusive": False,
        }
    )


@api_misc_bp.route("/api/v1/lists/<list_id>", methods=["GET", "PUT", "DELETE"])
@require_auth
def manage_list(list_id):
    if request.method == "DELETE":
        return "{}", 200
    return jsonify(
        {
            "id": list_id,
            "title": "List",
            "replies_policy": "list",
            "exclusive": False,
        }
    )


# ── Filters (stub) ───────────────────────────────────────────────


@api_misc_bp.route("/api/v2/filters", methods=["GET"])
@require_auth
def list_filters_v2():
    return jsonify([])


@api_misc_bp.route("/api/v2/filters", methods=["POST"])
@require_auth
def create_filter_v2():
    data = request.get_json(silent=True) or {}
    return jsonify(
        {
            "id": "1",
            "title": data.get("title", ""),
            "context": data.get("context", []),
            "expires_at": None,
            "filter_action": data.get("filter_action", "warn"),
            "keywords": [],
            "statuses": [],
        }
    )


@api_misc_bp.route("/api/v1/filters", methods=["GET"])
@require_auth
def list_filters_v1():
    return jsonify([])


# ── Suggestions ──────────────────────────────────────────────────


@api_misc_bp.route("/api/v2/suggestions", methods=["GET"])
@require_auth
def suggestions():
    return jsonify([])


@api_misc_bp.route("/api/v1/suggestions/<suggestion_id>", methods=["DELETE"])
@require_auth
def delete_suggestion(suggestion_id):
    return "{}", 200


# ── Trends ────────────────────────────────────────────────────────


@api_misc_bp.route("/api/v1/trends/tags", methods=["GET"])
def trending_tags():
    return jsonify([])


@api_misc_bp.route("/api/v1/trends/statuses", methods=["GET"])
def trending_statuses():
    return jsonify([])


@api_misc_bp.route("/api/v1/trends/links", methods=["GET"])
def trending_links():
    return jsonify([])


# ── Conversations ────────────────────────────────────────────────


@api_misc_bp.route("/api/v1/conversations", methods=["GET"])
@require_auth
def list_conversations():
    return jsonify([])


# ── Polls (stub) ─────────────────────────────────────────────────


@api_misc_bp.route("/api/v1/polls/<poll_id>", methods=["GET"])
def get_poll(poll_id):
    return jsonify({"error": "Record not found"}), 404


@api_misc_bp.route("/api/v1/polls/<poll_id>/votes", methods=["POST"])
@require_auth
def vote_poll(poll_id):
    return jsonify({"error": "Record not found"}), 404


# ── Push notifications (stub) ────────────────────────────────────


@api_misc_bp.route("/api/v1/push/subscription", methods=["GET"])
@require_auth
def get_push_subscription():
    return jsonify({"error": "Record not found"}), 404


@api_misc_bp.route("/api/v1/push/subscription", methods=["POST"])
@require_auth
def create_push_subscription():
    return jsonify({"error": "Web Push not supported"}), 422


@api_misc_bp.route("/api/v1/push/subscription", methods=["PUT"])
@require_auth
def update_push_subscription():
    return jsonify({"error": "Record not found"}), 404


@api_misc_bp.route("/api/v1/push/subscription", methods=["DELETE"])
@require_auth
def delete_push_subscription():
    return "{}", 200


# ── Reports ──────────────────────────────────────────────────────


@api_misc_bp.route("/api/v1/reports", methods=["POST"])
@require_auth
def create_report():
    return "{}", 200


# ── Muted / Blocked account lists ────────────────────────────────


@api_misc_bp.route("/api/v1/mutes", methods=["GET"])
@require_auth
def list_mutes():
    from models import Mute
    from utils.serializers import serialize_remote_account

    mutes = Mute.query.all()
    return jsonify(
        [serialize_remote_account(m.remote_account) for m in mutes if m.remote_account]
    )


@api_misc_bp.route("/api/v1/blocks", methods=["GET"])
@require_auth
def list_blocks():
    from models import Block
    from utils.serializers import serialize_remote_account

    blocks = Block.query.all()
    return jsonify(
        [
            serialize_remote_account(b.remote_account)
            for b in blocks
            if b.remote_account
        ]
    )


@api_misc_bp.route("/api/v1/domain_blocks", methods=["GET"])
@require_auth
def list_domain_blocks():
    return jsonify([])


@api_misc_bp.route("/api/v1/followed_tags", methods=["GET"])
@require_auth
def followed_tags():
    return jsonify([])
