"""
ActivityPub endpoints: actor, inbox, outbox, followers, following.
"""

import json
import logging
import time

from flask import Blueprint, request, jsonify, Response
import config
from models import db, Status, Follower, Following, RemoteAccount, Notification, Favourite
from utils.federation import (
    build_actor_object,
    build_note_object,
    fetch_remote_actor,
    deliver_to_inbox,
)

logger = logging.getLogger(__name__)

activitypub_bp = Blueprint("activitypub", __name__)

AP_CONTENT_TYPE = "application/activity+json; charset=utf-8"


def _ap_response(data, status=200):
    return Response(
        json.dumps(data),
        status=status,
        content_type=AP_CONTENT_TYPE,
    )


# ── Actor ─────────────────────────────────────────────────────────


@activitypub_bp.route("/users/<username>", methods=["GET"])
def actor(username):
    if username != config.USERNAME:
        return jsonify({"error": "Not found"}), 404
    accept = request.headers.get("Accept", "")
    if "activity+json" not in accept and "ld+json" not in accept:
        # Redirect browsers to a profile page
        return jsonify(build_actor_object())
    return _ap_response(build_actor_object())


@activitypub_bp.route("/@<username>", methods=["GET"])
def actor_at(username):
    """Profile URL — redirect or show actor for AP clients."""
    if username != config.USERNAME:
        return jsonify({"error": "Not found"}), 404
    accept = request.headers.get("Accept", "")
    if "activity+json" in accept or "ld+json" in accept:
        return _ap_response(build_actor_object())
    # For HTML clients, return a simple profile
    return f"<h1>@{config.USERNAME}@{config.DOMAIN}</h1><p>{config.BIO}</p>", 200


# ── Inbox (receiving activities) ──────────────────────────────────


@activitypub_bp.route("/users/<username>/inbox", methods=["POST"])
@activitypub_bp.route("/inbox", methods=["POST"])
def inbox(username=None):
    if username and username != config.USERNAME:
        return jsonify({"error": "Not found"}), 404

    # Optionally verify HTTP signature (best-effort)
    try:
        from utils.crypto import verify_http_signature
        verify_http_signature(
            request.method, request.path, dict(request.headers), request.data
        )
    except Exception as e:
        logger.warning("Signature verification failed: %s", e)
        # Continue anyway for now — many implementations are lenient

    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    activity_type = data.get("type", "")
    logger.info("Received activity: %s from %s", activity_type, data.get("actor"))

    if activity_type == "Follow":
        _handle_follow(data)
    elif activity_type == "Undo":
        _handle_undo(data)
    elif activity_type == "Create":
        _handle_create(data)
    elif activity_type == "Delete":
        _handle_delete(data)
    elif activity_type == "Like":
        _handle_like(data)
    elif activity_type == "Announce":
        _handle_announce(data)
    elif activity_type == "Update":
        _handle_update(data)
    elif activity_type == "Accept":
        _handle_accept(data)
    elif activity_type == "Reject":
        _handle_reject(data)
    else:
        logger.info("Ignoring activity type: %s", activity_type)

    return "", 202


def _handle_follow(data):
    actor_uri = data.get("actor")
    if not actor_uri:
        return
    ra = fetch_remote_actor(actor_uri)
    if not ra:
        return

    # Check if already following
    existing = Follower.query.filter_by(remote_account_id=ra.id).first()
    if not existing:
        follower = Follower(remote_account_id=ra.id, approved=True)
        db.session.add(follower)
        notif = Notification(type="follow", remote_account_id=ra.id)
        db.session.add(notif)
        db.session.commit()

    # Send Accept
    base = f"https://{config.DOMAIN}"
    accept_activity = {
        "@context": "https://www.w3.org/ns/activitystreams",
        "id": f"{base}/users/{config.USERNAME}/activities/accept-{int(time.time())}",
        "type": "Accept",
        "actor": f"{base}/users/{config.USERNAME}",
        "object": data,
    }
    deliver_to_inbox(ra.inbox_url, accept_activity)


def _handle_undo(data):
    obj = data.get("object", {})
    if isinstance(obj, str):
        return
    obj_type = obj.get("type", "")

    if obj_type == "Follow":
        actor_uri = data.get("actor")
        ra = RemoteAccount.query.filter_by(uri=actor_uri).first()
        if ra:
            Follower.query.filter_by(remote_account_id=ra.id).delete()
            db.session.commit()
    elif obj_type == "Like":
        # Undo favourite
        actor_uri = data.get("actor")
        ra = RemoteAccount.query.filter_by(uri=actor_uri).first()
        if ra:
            favs = Favourite.query.filter_by(
                remote_account_id=ra.id, local=False
            ).all()
            for fav in favs:
                status = fav.status
                if status:
                    status.favourites_count = max(0, status.favourites_count - 1)
                db.session.delete(fav)
            db.session.commit()


def _handle_create(data):
    obj = data.get("object", {})
    if isinstance(obj, str):
        return
    if obj.get("type") not in ("Note", "Article"):
        return

    actor_uri = data.get("actor") or obj.get("attributedTo")
    ra = fetch_remote_actor(actor_uri) if actor_uri else None

    # Check if this is a reply to one of our posts
    in_reply_to = obj.get("inReplyTo")
    in_reply_to_id = None
    is_mention = False
    if in_reply_to:
        base = f"https://{config.DOMAIN}"
        if in_reply_to.startswith(base):
            # Reply to our status
            parts = in_reply_to.rstrip("/").split("/")
            try:
                in_reply_to_id = int(parts[-1])
                is_mention = True
            except ValueError:
                pass

    # Store the remote status
    existing = Status.query.filter_by(uri=obj.get("id", "")).first()
    if existing:
        return

    content = obj.get("content", "")
    status = Status(
        uri=obj.get("id", f"remote-{int(time.time())}"),
        content=content,
        spoiler_text=obj.get("summary", ""),
        visibility="public",
        sensitive=obj.get("sensitive", False),
        remote=True,
        remote_account_id=ra.id if ra else None,
        remote_url=obj.get("url", obj.get("id")),
        in_reply_to_id=in_reply_to_id,
        in_reply_to_uri=in_reply_to,
        created_at=int(time.time()),
    )
    db.session.add(status)
    db.session.commit()

    # Update reply count on parent
    if in_reply_to_id:
        parent = db.session.get(Status, in_reply_to_id)
        if parent:
            parent.replies_count = (parent.replies_count or 0) + 1
            db.session.commit()

    # Create notification for mentions/replies to our posts
    if is_mention and ra:
        notif = Notification(
            type="mention", remote_account_id=ra.id, status_id=status.id
        )
        db.session.add(notif)
        db.session.commit()


def _handle_delete(data):
    obj = data.get("object", {})
    obj_id = obj if isinstance(obj, str) else obj.get("id", "")
    if obj_id:
        status = Status.query.filter_by(uri=obj_id, remote=True).first()
        if status:
            status.deleted_at = int(time.time())
            db.session.commit()


def _handle_like(data):
    actor_uri = data.get("actor")
    obj_id = data.get("object")
    if not actor_uri or not obj_id:
        return
    ra = fetch_remote_actor(actor_uri)
    if not ra:
        return
    status = Status.query.filter_by(uri=obj_id).first()
    if not status:
        return
    existing = Favourite.query.filter_by(
        status_id=status.id, remote_account_id=ra.id
    ).first()
    if not existing:
        fav = Favourite(status_id=status.id, remote_account_id=ra.id, local=False)
        db.session.add(fav)
        status.favourites_count = (status.favourites_count or 0) + 1
        notif = Notification(
            type="favourite", remote_account_id=ra.id, status_id=status.id
        )
        db.session.add(notif)
        db.session.commit()


def _handle_announce(data):
    actor_uri = data.get("actor")
    obj_id = data.get("object")
    if not actor_uri or not obj_id:
        return
    ra = fetch_remote_actor(actor_uri)
    if not ra:
        return
    if isinstance(obj_id, str):
        status = Status.query.filter_by(uri=obj_id).first()
        if status:
            status.reblogs_count = (status.reblogs_count or 0) + 1
            notif = Notification(
                type="reblog", remote_account_id=ra.id, status_id=status.id
            )
            db.session.add(notif)
            db.session.commit()


def _handle_update(data):
    obj = data.get("object", {})
    if isinstance(obj, str):
        return
    if obj.get("type") in ("Note", "Article"):
        existing = Status.query.filter_by(uri=obj.get("id", "")).first()
        if existing:
            existing.content = obj.get("content", existing.content)
            existing.spoiler_text = obj.get("summary", existing.spoiler_text)
            existing.sensitive = obj.get("sensitive", existing.sensitive)
            existing.updated_at = int(time.time())
            db.session.commit()
    elif obj.get("type") == "Person":
        # Actor update
        ra = RemoteAccount.query.filter_by(uri=obj.get("id", "")).first()
        if ra:
            ra.display_name = obj.get("name", ra.display_name)
            ra.bio = obj.get("summary", ra.bio)
            ra.avatar_url = (obj.get("icon") or {}).get("url", ra.avatar_url)
            ra.header_url = (obj.get("image") or {}).get("url", ra.header_url)
            ra.public_key_pem = (obj.get("publicKey") or {}).get(
                "publicKeyPem", ra.public_key_pem
            )
            ra.updated_at = int(time.time())
            db.session.commit()


def _handle_accept(data):
    """Handle Accept of our Follow request."""
    obj = data.get("object", {})
    if isinstance(obj, dict) and obj.get("type") == "Follow":
        # Mark our following as approved
        actor_uri = data.get("actor")
        ra = RemoteAccount.query.filter_by(uri=actor_uri).first()
        if ra:
            following = Following.query.filter_by(remote_account_id=ra.id).first()
            if following:
                following.approved = True
                db.session.commit()


def _handle_reject(data):
    """Handle Reject of our Follow request."""
    obj = data.get("object", {})
    if isinstance(obj, dict) and obj.get("type") == "Follow":
        actor_uri = data.get("actor")
        ra = RemoteAccount.query.filter_by(uri=actor_uri).first()
        if ra:
            Following.query.filter_by(remote_account_id=ra.id).delete()
            db.session.commit()


# ── Outbox ────────────────────────────────────────────────────────


@activitypub_bp.route("/users/<username>/outbox", methods=["GET"])
def outbox(username):
    if username != config.USERNAME:
        return jsonify({"error": "Not found"}), 404

    base = f"https://{config.DOMAIN}"
    statuses = (
        Status.query.filter_by(remote=False, deleted_at=None)
        .filter(Status.visibility.in_(["public", "unlisted"]))
        .order_by(Status.id.desc())
        .limit(20)
        .all()
    )

    items = []
    for s in statuses:
        note = build_note_object(s)
        items.append(
            {
                "id": f"{base}/users/{config.USERNAME}/activities/create-{s.id}",
                "type": "Create",
                "actor": f"{base}/users/{config.USERNAME}",
                "published": note["published"],
                "to": note["to"],
                "cc": note.get("cc", []),
                "object": note,
            }
        )

    total = Status.query.filter_by(remote=False, deleted_at=None).count()

    return _ap_response(
        {
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": f"{base}/users/{config.USERNAME}/outbox",
            "type": "OrderedCollection",
            "totalItems": total,
            "orderedItems": items,
        }
    )


# ── Followers / Following collections ────────────────────────────


@activitypub_bp.route("/users/<username>/followers", methods=["GET"])
def followers_collection(username):
    if username != config.USERNAME:
        return jsonify({"error": "Not found"}), 404
    base = f"https://{config.DOMAIN}"
    count = Follower.query.filter_by(approved=True).count()
    return _ap_response(
        {
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": f"{base}/users/{config.USERNAME}/followers",
            "type": "OrderedCollection",
            "totalItems": count,
            "orderedItems": [],
        }
    )


@activitypub_bp.route("/users/<username>/following", methods=["GET"])
def following_collection(username):
    if username != config.USERNAME:
        return jsonify({"error": "Not found"}), 404
    base = f"https://{config.DOMAIN}"
    count = Following.query.filter_by(approved=True).count()
    return _ap_response(
        {
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": f"{base}/users/{config.USERNAME}/following",
            "type": "OrderedCollection",
            "totalItems": count,
            "orderedItems": [],
        }
    )
