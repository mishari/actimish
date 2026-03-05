"""
Mastodon API: Status (post) endpoints.
"""

import time

from flask import Blueprint, request, jsonify
import bleach
import config
from models import (
    db,
    Status,
    MediaAttachment,
    Favourite,
    Bookmark,
    Notification,
    IdempotencyKey,
    RemoteAccount,
)
from utils.auth import require_auth, optional_auth
from utils.serializers import serialize_status
from utils.serializers import _plaintext_from_html
from utils.federation import (
    build_note_object,
    deliver_to_followers,
    deliver_to_inbox,
)

api_statuses_bp = Blueprint("api_statuses", __name__)


def _parse_int(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


@api_statuses_bp.route("/api/v1/statuses", methods=["POST"])
@require_auth
def create_status():
    """Create a new status."""
    data = request.get_json(silent=True) or {}
    if not data:
        data = request.form.to_dict(flat=False)
        # Flatten single-value lists
        data = {k: v[0] if isinstance(v, list) and len(v) == 1 else v for k, v in data.items()}

    # Check idempotency
    idem_key = request.headers.get("Idempotency-Key")
    if idem_key:
        existing = IdempotencyKey.query.filter_by(key=idem_key).first()
        if existing and existing.status_id:
            status = db.session.get(Status, existing.status_id)
            if status:
                return jsonify(serialize_status(status, for_account="local"))

    text = data.get("status", "")
    spoiler_text = data.get("spoiler_text", "")
    visibility = data.get("visibility", "public")
    sensitive = data.get("sensitive", False)
    if isinstance(sensitive, str):
        sensitive = sensitive.lower() in ("true", "1", "yes")
    language = data.get("language", "en")
    in_reply_to_id = data.get("in_reply_to_id")
    media_ids = data.get("media_ids", []) or data.get("media_ids[]", [])
    if isinstance(media_ids, str):
        media_ids = [media_ids]

    # Sanitize HTML (allow basic formatting)
    allowed_tags = [
        "a", "br", "p", "span", "strong", "em", "b", "i", "u", "s",
        "blockquote", "pre", "code", "ul", "ol", "li", "h1", "h2", "h3",
    ]
    allowed_attrs = {"a": ["href", "rel", "class"], "span": ["class"]}

    # Wrap plain text in <p> tags if it doesn't contain HTML
    if "<" not in text and text:
        # Convert newlines to <br>
        content = "<p>" + text.replace("\n\n", "</p><p>").replace("\n", "<br>") + "</p>"
    else:
        content = text

    content = bleach.clean(content, tags=allowed_tags, attributes=allowed_attrs)

    base = f"https://{config.DOMAIN}"

    # Determine in_reply_to_uri
    in_reply_to_uri = None
    if in_reply_to_id:
        try:
            parent = db.session.get(Status, int(in_reply_to_id))
            if parent:
                in_reply_to_uri = parent.uri
                in_reply_to_id = parent.id
        except (ValueError, TypeError):
            in_reply_to_id = None

    status = Status(
        uri="",  # Will set after we have the ID
        content=content,
        spoiler_text=spoiler_text,
        visibility=visibility,
        sensitive=sensitive,
        language=language,
        in_reply_to_id=int(in_reply_to_id) if in_reply_to_id else None,
        in_reply_to_uri=in_reply_to_uri,
        remote=False,
    )
    db.session.add(status)
    db.session.flush()  # Get the ID

    # Set the URI
    status.uri = f"{base}/users/{config.USERNAME}/statuses/{status.id}"

    # Attach media
    if media_ids:
        for mid in media_ids:
            try:
                media = db.session.get(MediaAttachment, int(mid))
                if media and media.status_id is None:
                    media.status_id = status.id
            except (ValueError, TypeError):
                pass

    # Update reply count on parent
    if status.in_reply_to_id:
        parent = db.session.get(Status, status.in_reply_to_id)
        if parent:
            parent.replies_count = (parent.replies_count or 0) + 1

    # Store idempotency key
    if idem_key:
        ik = IdempotencyKey(key=idem_key, status_id=status.id)
        db.session.add(ik)

    db.session.commit()

    # Federate: send Create activity to followers
    if visibility in ("public", "unlisted"):
        note = build_note_object(status)
        activity = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": f"{base}/users/{config.USERNAME}/activities/create-{status.id}",
            "type": "Create",
            "actor": f"{base}/users/{config.USERNAME}",
            "published": note["published"],
            "to": note["to"],
            "cc": note.get("cc", []),
            "object": note,
        }
        deliver_to_followers(activity)

    return jsonify(serialize_status(status, for_account="local")), 200


@api_statuses_bp.route("/api/v1/statuses/<status_id>", methods=["GET"])
@optional_auth
def get_status(status_id):
    sid = _parse_int(status_id)
    if sid is None:
        return jsonify({"error": "Record not found"}), 404
    status = db.session.get(Status, sid)
    if not status or status.deleted_at:
        return jsonify({"error": "Record not found"}), 404

    # Hide non-public content from unauthenticated requests.
    if not request.oauth_token and status.visibility not in ("public", "unlisted"):
        return jsonify({"error": "Record not found"}), 404

    account = "local" if request.oauth_token else None
    return jsonify(serialize_status(status, for_account=account))


@api_statuses_bp.route("/api/v1/statuses/<status_id>", methods=["DELETE"])
@require_auth
def delete_status(status_id):
    sid = _parse_int(status_id)
    if sid is None:
        return jsonify({"error": "Record not found"}), 404
    status = db.session.get(Status, sid)
    if not status or status.remote:
        return jsonify({"error": "Record not found"}), 404

    # Return the status with text for "delete and redraft"
    result = serialize_status(status, for_account="local")
    # Include the source text
    result["text"] = _plaintext_from_html(status.content)

    status.deleted_at = int(time.time())
    db.session.commit()

    # Send Delete to followers
    base = f"https://{config.DOMAIN}"
    delete_activity = {
        "@context": "https://www.w3.org/ns/activitystreams",
        "id": f"{base}/users/{config.USERNAME}/activities/delete-{status.id}",
        "type": "Delete",
        "actor": f"{base}/users/{config.USERNAME}",
        "object": status.uri,
        "to": ["https://www.w3.org/ns/activitystreams#Public"],
    }
    deliver_to_followers(delete_activity)

    return jsonify(result)


@api_statuses_bp.route("/api/v1/statuses/<status_id>", methods=["PUT"])
@require_auth
def edit_status(status_id):
    sid = _parse_int(status_id)
    if sid is None:
        return jsonify({"error": "Record not found"}), 404
    status = db.session.get(Status, sid)
    if not status or status.remote or status.deleted_at:
        return jsonify({"error": "Record not found"}), 404

    data = request.get_json(silent=True) or request.form.to_dict()
    if "status" in data:
        text = data["status"]
        if "<" not in text and text:
            content = "<p>" + text.replace("\n\n", "</p><p>").replace("\n", "<br>") + "</p>"
        else:
            content = text
        allowed_tags = [
            "a", "br", "p", "span", "strong", "em", "b", "i", "u", "s",
            "blockquote", "pre", "code", "ul", "ol", "li",
        ]
        content = bleach.clean(content, tags=allowed_tags, attributes={"a": ["href", "rel", "class"]})
        status.content = content
    if "spoiler_text" in data:
        status.spoiler_text = data["spoiler_text"]
    if "sensitive" in data:
        val = data["sensitive"]
        status.sensitive = val if isinstance(val, bool) else str(val).lower() in ("true", "1")
    if "language" in data:
        status.language = data["language"]

    status.updated_at = int(time.time())
    db.session.commit()

    # Send Update to followers
    base = f"https://{config.DOMAIN}"
    note = build_note_object(status)
    update_activity = {
        "@context": "https://www.w3.org/ns/activitystreams",
        "id": f"{base}/users/{config.USERNAME}/activities/update-{status.id}-{int(time.time())}",
        "type": "Update",
        "actor": f"{base}/users/{config.USERNAME}",
        "object": note,
        "to": note["to"],
        "cc": note.get("cc", []),
    }
    deliver_to_followers(update_activity)

    return jsonify(serialize_status(status, for_account="local"))


@api_statuses_bp.route("/api/v1/statuses/<status_id>/source", methods=["GET"])
@require_auth
def status_source(status_id):
    sid = _parse_int(status_id)
    if sid is None:
        return jsonify({"error": "Record not found"}), 404
    status = db.session.get(Status, sid)
    if not status or status.deleted_at:
        return jsonify({"error": "Record not found"}), 404
    return jsonify(
        {
            "id": str(status.id),
            "text": _plaintext_from_html(status.content),
            "spoiler_text": status.spoiler_text or "",
        }
    )


@api_statuses_bp.route("/api/v1/statuses/<status_id>/context", methods=["GET"])
@optional_auth
def status_context(status_id):
    sid = _parse_int(status_id)
    if sid is None:
        return jsonify({"error": "Record not found"}), 404
    status = db.session.get(Status, sid)
    if not status or status.deleted_at:
        return jsonify({"error": "Record not found"}), 404

    account = "local" if request.oauth_token else None

    # Get ancestors (walk up the reply chain)
    ancestors = []
    current = status
    while current.in_reply_to_id:
        parent = db.session.get(Status, current.in_reply_to_id)
        if not parent or parent.deleted_at:
            break
        ancestors.insert(0, serialize_status(parent, for_account=account))
        current = parent

    # Get descendants (all replies)
    descendants = []
    _get_descendants(status.id, descendants, account)

    return jsonify({"ancestors": ancestors, "descendants": descendants})


def _get_descendants(status_id, result, account, depth=0):
    if depth > 20:
        return
    replies = (
        Status.query.filter_by(in_reply_to_id=status_id, deleted_at=None)
        .order_by(Status.id.asc())
        .all()
    )
    for reply in replies:
        result.append(serialize_status(reply, for_account=account))
        _get_descendants(reply.id, result, account, depth + 1)


@api_statuses_bp.route("/api/v1/statuses/<status_id>/history", methods=["GET"])
def status_history(status_id):
    sid = _parse_int(status_id)
    if sid is None:
        return jsonify({"error": "Record not found"}), 404
    status = db.session.get(Status, sid)
    if not status or status.deleted_at:
        return jsonify({"error": "Record not found"}), 404
    from utils.serializers import _epoch_to_iso

    return jsonify(
        [
            {
                "content": status.content,
                "spoiler_text": status.spoiler_text or "",
                "sensitive": status.sensitive,
                "created_at": _epoch_to_iso(status.created_at),
                "account": serialize_status(status)["account"],
                "media_attachments": serialize_status(status)["media_attachments"],
                "emojis": [],
            }
        ]
    )


# ── Interactions ──────────────────────────────────────────────────


@api_statuses_bp.route("/api/v1/statuses/<status_id>/favourite", methods=["POST"])
@require_auth
def favourite_status(status_id):
    sid = _parse_int(status_id)
    if sid is None:
        return jsonify({"error": "Record not found"}), 404
    status = db.session.get(Status, sid)
    if not status or status.deleted_at:
        return jsonify({"error": "Record not found"}), 404

    existing = Favourite.query.filter_by(status_id=status.id, local=True).first()
    if not existing:
        fav = Favourite(status_id=status.id, local=True)
        db.session.add(fav)
        status.favourites_count = (status.favourites_count or 0) + 1
        db.session.commit()

        # Federate Like to the status author if remote
        if status.remote and status.remote_account:
            base = f"https://{config.DOMAIN}"
            like_activity = {
                "@context": "https://www.w3.org/ns/activitystreams",
                "id": f"{base}/users/{config.USERNAME}/activities/like-{status.id}",
                "type": "Like",
                "actor": f"{base}/users/{config.USERNAME}",
                "object": status.uri,
            }
            deliver_to_inbox(status.remote_account.inbox_url, like_activity)

    return jsonify(serialize_status(status, for_account="local"))


@api_statuses_bp.route("/api/v1/statuses/<status_id>/unfavourite", methods=["POST"])
@require_auth
def unfavourite_status(status_id):
    sid = _parse_int(status_id)
    if sid is None:
        return jsonify({"error": "Record not found"}), 404
    status = db.session.get(Status, sid)
    if not status or status.deleted_at:
        return jsonify({"error": "Record not found"}), 404

    fav = Favourite.query.filter_by(status_id=status.id, local=True).first()
    if fav:
        db.session.delete(fav)
        status.favourites_count = max(0, (status.favourites_count or 0) - 1)
        db.session.commit()

        # Federate Undo Like
        if status.remote and status.remote_account:
            base = f"https://{config.DOMAIN}"
            undo_activity = {
                "@context": "https://www.w3.org/ns/activitystreams",
                "id": f"{base}/users/{config.USERNAME}/activities/undo-like-{status.id}",
                "type": "Undo",
                "actor": f"{base}/users/{config.USERNAME}",
                "object": {
                    "id": f"{base}/users/{config.USERNAME}/activities/like-{status.id}",
                    "type": "Like",
                    "actor": f"{base}/users/{config.USERNAME}",
                    "object": status.uri,
                },
            }
            deliver_to_inbox(status.remote_account.inbox_url, undo_activity)

    return jsonify(serialize_status(status, for_account="local"))


@api_statuses_bp.route("/api/v1/statuses/<status_id>/reblog", methods=["POST"])
@require_auth
def reblog_status(status_id):
    sid = _parse_int(status_id)
    if sid is None:
        return jsonify({"error": "Record not found"}), 404
    status = db.session.get(Status, sid)
    if not status or status.deleted_at:
        return jsonify({"error": "Record not found"}), 404

    # Check if already reblogged
    existing = Status.query.filter_by(
        reblog_of_id=status.id, remote=False, deleted_at=None
    ).first()
    if existing:
        return jsonify(serialize_status(existing, for_account="local"))

    base = f"https://{config.DOMAIN}"
    reblog = Status(
        uri="",
        content="",
        visibility=request.get_json(silent=True, force=True).get("visibility", "public") if request.data else "public",
        remote=False,
        reblog_of_id=status.id,
    )
    db.session.add(reblog)
    db.session.flush()
    reblog.uri = f"{base}/users/{config.USERNAME}/statuses/{reblog.id}"
    status.reblogs_count = (status.reblogs_count or 0) + 1
    db.session.commit()

    # Federate Announce
    announce_activity = {
        "@context": "https://www.w3.org/ns/activitystreams",
        "id": reblog.uri,
        "type": "Announce",
        "actor": f"{base}/users/{config.USERNAME}",
        "object": status.uri,
        "to": ["https://www.w3.org/ns/activitystreams#Public"],
        "cc": [f"{base}/users/{config.USERNAME}/followers"],
    }
    deliver_to_followers(announce_activity)
    if status.remote and status.remote_account:
        deliver_to_inbox(status.remote_account.inbox_url, announce_activity)

    return jsonify(serialize_status(reblog, for_account="local"))


@api_statuses_bp.route("/api/v1/statuses/<status_id>/unreblog", methods=["POST"])
@require_auth
def unreblog_status(status_id):
    sid = _parse_int(status_id)
    if sid is None:
        return jsonify({"error": "Record not found"}), 404
    status = db.session.get(Status, sid)
    if not status or status.deleted_at:
        return jsonify({"error": "Record not found"}), 404

    reblog = Status.query.filter_by(
        reblog_of_id=status.id, remote=False, deleted_at=None
    ).first()
    if reblog:
        reblog.deleted_at = int(time.time())
        status.reblogs_count = max(0, (status.reblogs_count or 0) - 1)
        db.session.commit()

        # Federate Undo Announce
        base = f"https://{config.DOMAIN}"
        undo_activity = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": f"{base}/users/{config.USERNAME}/activities/undo-announce-{status.id}",
            "type": "Undo",
            "actor": f"{base}/users/{config.USERNAME}",
            "object": {
                "id": reblog.uri,
                "type": "Announce",
                "actor": f"{base}/users/{config.USERNAME}",
                "object": status.uri,
            },
        }
        deliver_to_followers(undo_activity)

    return jsonify(serialize_status(status, for_account="local"))


@api_statuses_bp.route("/api/v1/statuses/<status_id>/bookmark", methods=["POST"])
@require_auth
def bookmark_status(status_id):
    sid = _parse_int(status_id)
    if sid is None:
        return jsonify({"error": "Record not found"}), 404
    status = db.session.get(Status, sid)
    if not status or status.deleted_at:
        return jsonify({"error": "Record not found"}), 404
    existing = Bookmark.query.filter_by(status_id=status.id).first()
    if not existing:
        bm = Bookmark(status_id=status.id)
        db.session.add(bm)
        db.session.commit()
    return jsonify(serialize_status(status, for_account="local"))


@api_statuses_bp.route("/api/v1/statuses/<status_id>/unbookmark", methods=["POST"])
@require_auth
def unbookmark_status(status_id):
    sid = _parse_int(status_id)
    if sid is None:
        return jsonify({"error": "Record not found"}), 404
    status = db.session.get(Status, sid)
    if not status or status.deleted_at:
        return jsonify({"error": "Record not found"}), 404
    Bookmark.query.filter_by(status_id=status.id).delete()
    db.session.commit()
    return jsonify(serialize_status(status, for_account="local"))


@api_statuses_bp.route("/api/v1/statuses/<status_id>/mute", methods=["POST"])
@require_auth
def mute_conversation(status_id):
    sid = _parse_int(status_id)
    if sid is None:
        return jsonify({"error": "Record not found"}), 404
    status = db.session.get(Status, sid)
    if not status or status.deleted_at:
        return jsonify({"error": "Record not found"}), 404
    # We don't actually track muted conversations yet; just return the status
    result = serialize_status(status, for_account="local")
    result["muted"] = True
    return jsonify(result)


@api_statuses_bp.route("/api/v1/statuses/<status_id>/unmute", methods=["POST"])
@require_auth
def unmute_conversation(status_id):
    sid = _parse_int(status_id)
    if sid is None:
        return jsonify({"error": "Record not found"}), 404
    status = db.session.get(Status, sid)
    if not status or status.deleted_at:
        return jsonify({"error": "Record not found"}), 404
    return jsonify(serialize_status(status, for_account="local"))


@api_statuses_bp.route("/api/v1/statuses/<status_id>/pin", methods=["POST"])
@require_auth
def pin_status(status_id):
    sid = _parse_int(status_id)
    if sid is None:
        return jsonify({"error": "Record not found"}), 404
    status = db.session.get(Status, sid)
    if not status or status.remote or status.deleted_at:
        return jsonify({"error": "Record not found"}), 404
    status.pinned = True
    db.session.commit()
    return jsonify(serialize_status(status, for_account="local"))


@api_statuses_bp.route("/api/v1/statuses/<status_id>/unpin", methods=["POST"])
@require_auth
def unpin_status(status_id):
    sid = _parse_int(status_id)
    if sid is None:
        return jsonify({"error": "Record not found"}), 404
    status = db.session.get(Status, sid)
    if not status or status.deleted_at:
        return jsonify({"error": "Record not found"}), 404
    status.pinned = False
    db.session.commit()
    return jsonify(serialize_status(status, for_account="local"))


@api_statuses_bp.route("/api/v1/statuses/<status_id>/favourited_by", methods=["GET"])
def favourited_by(status_id):
    sid = _parse_int(status_id)
    if sid is None:
        return jsonify({"error": "Record not found"}), 404
    status = db.session.get(Status, sid)
    if not status or status.deleted_at:
        return jsonify({"error": "Record not found"}), 404
    favs = Favourite.query.filter_by(status_id=status.id, local=False).all()
    from utils.serializers import serialize_remote_account
    return jsonify(
        [serialize_remote_account(f.remote_account) for f in favs if f.remote_account]
    )


@api_statuses_bp.route("/api/v1/statuses/<status_id>/reblogged_by", methods=["GET"])
def reblogged_by(status_id):
    # Not fully tracking remote reblogs yet
    return jsonify([])
