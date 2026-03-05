"""
Mastodon API: Account endpoints.
"""

from flask import Blueprint, request, jsonify
import config
from models import (
    db,
    Status,
    Follower,
    Following,
    RemoteAccount,
    Block,
    Mute,
    Notification,
)
from utils.auth import require_auth, optional_auth
from utils.serializers import (
    serialize_credential_account,
    serialize_account_local,
    serialize_remote_account,
    serialize_status,
    serialize_relationship,
)

api_accounts_bp = Blueprint("api_accounts", __name__)


def _parse_int(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _parse_int_default(value, default):
    parsed = _parse_int(value)
    return default if parsed is None else parsed


@api_accounts_bp.route("/api/v1/accounts/verify_credentials", methods=["GET"])
@require_auth
def verify_credentials():
    return jsonify(serialize_credential_account())


@api_accounts_bp.route("/api/v1/accounts/update_credentials", methods=["PATCH"])
@require_auth
def update_credentials():
    """Update profile (display name, bio, avatar, header)."""
    import os
    from PIL import Image
    from io import BytesIO
    from utils.settings import update_settings
    from utils.media import detect_mime

    data = request.form.to_dict()

    # Update display_name and bio in config and settings
    if "display_name" in data:
        config.DISPLAY_NAME = data["display_name"]
        update_settings(display_name=data["display_name"])
    if "note" in data:
        config.BIO = data["note"]
        update_settings(bio=data["note"])

    # Handle avatar upload
    if "avatar" in request.files:
        f = request.files["avatar"]
        if f and f.filename:
            try:
                # Read file content
                file_data = f.read()
                f.seek(0)

                # Detect MIME type
                mime_type = detect_mime(file_data, f.filename)
                if mime_type not in config.ALLOWED_IMAGE_TYPES:
                    return jsonify({"error": "Invalid image type"}), 400

                # Determine file extension
                ext_map = {
                    "image/jpeg": "jpg",
                    "image/png": "png",
                    "image/gif": "gif",
                    "image/webp": "webp",
                }
                ext = ext_map.get(mime_type, "png")

                # Open image and resize if needed
                img = Image.open(BytesIO(file_data))
                max_dim = 400
                if img.width > max_dim or img.height > max_dim:
                    img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

                # Save avatar with correct extension
                avatar_path = os.path.join(config.DATA_DIR, f"avatar.{ext}")
                
                # Remove old avatar files if extension changed
                for old_ext in ["png", "jpg", "jpeg", "gif", "webp"]:
                    old_path = os.path.join(config.DATA_DIR, f"avatar.{old_ext}")
                    if old_path != avatar_path and os.path.exists(old_path):
                        os.remove(old_path)

                img.save(avatar_path)

                # Store MIME type in settings
                update_settings(avatar_mime=mime_type)
            except Exception as e:
                return jsonify({"error": f"Failed to process avatar: {str(e)}"}), 400

    # Handle header upload
    if "header" in request.files:
        f = request.files["header"]
        if f and f.filename:
            try:
                # Read file content
                file_data = f.read()
                f.seek(0)

                # Detect MIME type
                mime_type = detect_mime(file_data, f.filename)
                if mime_type not in config.ALLOWED_IMAGE_TYPES:
                    return jsonify({"error": "Invalid image type"}), 400

                # Determine file extension
                ext_map = {
                    "image/jpeg": "jpg",
                    "image/png": "png",
                    "image/gif": "gif",
                    "image/webp": "webp",
                }
                ext = ext_map.get(mime_type, "png")

                # Open image and resize if needed
                img = Image.open(BytesIO(file_data))
                max_dim = 400
                if img.width > max_dim or img.height > max_dim:
                    img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

                # Save header with correct extension
                header_path = os.path.join(config.DATA_DIR, f"header.{ext}")
                
                # Remove old header files if extension changed
                for old_ext in ["png", "jpg", "jpeg", "gif", "webp"]:
                    old_path = os.path.join(config.DATA_DIR, f"header.{old_ext}")
                    if old_path != header_path and os.path.exists(old_path):
                        os.remove(old_path)

                img.save(header_path)

                # Store MIME type in settings
                update_settings(header_mime=mime_type)
            except Exception as e:
                return jsonify({"error": f"Failed to process header: {str(e)}"}), 400

    return jsonify(serialize_credential_account())


@api_accounts_bp.route("/api/v1/accounts/lookup", methods=["GET"])
def account_lookup():
    acct = request.args.get("acct", "")
    if acct == config.USERNAME or acct == f"{config.USERNAME}@{config.DOMAIN}":
        return jsonify(serialize_account_local())
    # Check remote accounts
    if "@" in acct:
        parts = acct.split("@")
        ra = RemoteAccount.query.filter_by(
            username=parts[0], domain=parts[1]
        ).first()
        if ra:
            return jsonify(serialize_remote_account(ra))
    return jsonify({"error": "Record not found"}), 404


@api_accounts_bp.route("/api/v1/accounts/search", methods=["GET"])
def accounts_search():
    q = request.args.get("q", "")
    limit = min(_parse_int_default(request.args.get("limit"), 40), 80)
    results = []

    if config.USERNAME.startswith(q) or config.DISPLAY_NAME.lower().startswith(q.lower()):
        results.append(serialize_account_local())

    remote = RemoteAccount.query.filter(
        (RemoteAccount.username.ilike(f"%{q}%"))
        | (RemoteAccount.display_name.ilike(f"%{q}%"))
    ).limit(limit).all()
    for ra in remote:
        results.append(serialize_remote_account(ra))

    return jsonify(results[:limit])


@api_accounts_bp.route("/api/v1/accounts/relationships", methods=["GET"])
@require_auth
def relationships():
    ids = request.args.getlist("id[]") or request.args.getlist("id")
    results = []
    for aid in ids:
        try:
            aid_int = int(aid)
        except ValueError:
            continue
        is_following = Following.query.filter_by(
            remote_account_id=aid_int, approved=True
        ).first() is not None
        is_followed_by = Follower.query.filter_by(
            remote_account_id=aid_int, approved=True
        ).first() is not None
        is_blocking = Block.query.filter_by(remote_account_id=aid_int).first() is not None
        is_muting = Mute.query.filter_by(remote_account_id=aid_int).first() is not None
        results.append(
            serialize_relationship(
                aid_int,
                is_following=is_following,
                is_followed_by=is_followed_by,
                is_blocking=is_blocking,
                is_muting=is_muting,
            )
        )
    return jsonify(results)


@api_accounts_bp.route("/api/v1/accounts/familiar_followers", methods=["GET"])
@require_auth
def familiar_followers():
    ids = request.args.getlist("id[]") or request.args.getlist("id")
    return jsonify([{"id": aid, "accounts": []} for aid in ids])


@api_accounts_bp.route("/api/v1/accounts/<account_id>", methods=["GET"])
def get_account(account_id):
    if account_id == "1":
        return jsonify(serialize_account_local())
    aid = _parse_int(account_id)
    if aid is None:
        return jsonify({"error": "Record not found"}), 404
    ra = db.session.get(RemoteAccount, aid)
    if ra:
        return jsonify(serialize_remote_account(ra))
    return jsonify({"error": "Record not found"}), 404


@api_accounts_bp.route("/api/v1/accounts/<account_id>/statuses", methods=["GET"])
def account_statuses(account_id):
    limit = min(_parse_int_default(request.args.get("limit"), 20), 40)
    max_id = request.args.get("max_id")
    min_id = request.args.get("min_id")
    since_id = request.args.get("since_id")
    only_media = request.args.get("only_media") == "true"
    exclude_replies = request.args.get("exclude_replies") == "true"
    exclude_reblogs = request.args.get("exclude_reblogs") == "true"
    pinned = request.args.get("pinned") == "true"

    if account_id == "1":
        query = Status.query.filter_by(remote=False, deleted_at=None)
    else:
        aid = _parse_int(account_id)
        if aid is None:
            return jsonify({"error": "Record not found"}), 404
        ra = db.session.get(RemoteAccount, aid)
        if not ra:
            return jsonify({"error": "Record not found"}), 404
        query = Status.query.filter_by(
            remote=True, remote_account_id=ra.id, deleted_at=None
        )

    if pinned:
        query = query.filter_by(pinned=True)
    if exclude_replies:
        query = query.filter(Status.in_reply_to_id.is_(None))
    if exclude_reblogs:
        query = query.filter(Status.reblog_of_id.is_(None))
    try:
        if max_id:
            query = query.filter(Status.id < int(max_id))
        if min_id:
            query = query.filter(Status.id > int(min_id))
        if since_id:
            query = query.filter(Status.id > int(since_id))
    except ValueError:
        pass

    statuses = query.order_by(Status.id.desc()).limit(limit).all()

    if only_media:
        statuses = [s for s in statuses if s.media_attachments]

    result = [serialize_status(s, for_account="local") for s in statuses]

    response = jsonify(result)
    _add_pagination_headers(response, statuses, request.path)
    return response


@api_accounts_bp.route("/api/v1/accounts/<account_id>/followers", methods=["GET"])
def account_followers(account_id):
    if account_id != "1":
        return jsonify([])
    limit = min(_parse_int_default(request.args.get("limit"), 40), 80)
    followers = Follower.query.filter_by(approved=True).limit(limit).all()
    return jsonify(
        [serialize_remote_account(f.remote_account) for f in followers if f.remote_account]
    )


@api_accounts_bp.route("/api/v1/accounts/<account_id>/following", methods=["GET"])
def account_following(account_id):
    if account_id != "1":
        return jsonify([])
    limit = min(_parse_int_default(request.args.get("limit"), 40), 80)
    following = Following.query.filter_by(approved=True).limit(limit).all()
    return jsonify(
        [serialize_remote_account(f.remote_account) for f in following if f.remote_account]
    )


@api_accounts_bp.route("/api/v1/accounts/<account_id>/follow", methods=["POST"])
@require_auth
def follow_account(account_id):
    aid = _parse_int(account_id)
    if aid is None:
        return jsonify({"error": "Record not found"}), 404
    ra = db.session.get(RemoteAccount, aid)
    if not ra:
        return jsonify({"error": "Record not found"}), 404

    existing = Following.query.filter_by(remote_account_id=ra.id).first()
    if not existing:
        following = Following(remote_account_id=ra.id, approved=False)
        db.session.add(following)
        db.session.commit()

        # Send Follow activity
        import time
        from utils.federation import deliver_to_inbox

        base = f"https://{config.DOMAIN}"
        follow_activity = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": f"{base}/users/{config.USERNAME}/activities/follow-{int(time.time())}",
            "type": "Follow",
            "actor": f"{base}/users/{config.USERNAME}",
            "object": ra.uri,
        }
        deliver_to_inbox(ra.inbox_url, follow_activity)

    is_followed_by = Follower.query.filter_by(
        remote_account_id=ra.id, approved=True
    ).first() is not None
    return jsonify(
        serialize_relationship(
            ra.id,
            is_following=True,
            is_followed_by=is_followed_by,
        )
    )


@api_accounts_bp.route("/api/v1/accounts/<account_id>/unfollow", methods=["POST"])
@require_auth
def unfollow_account(account_id):
    aid = _parse_int(account_id)
    if aid is None:
        return jsonify({"error": "Record not found"}), 404
    ra = db.session.get(RemoteAccount, aid)
    if not ra:
        return jsonify({"error": "Record not found"}), 404

    following = Following.query.filter_by(remote_account_id=ra.id).first()
    if following:
        db.session.delete(following)
        db.session.commit()

        # Send Undo Follow
        import time
        from utils.federation import deliver_to_inbox

        base = f"https://{config.DOMAIN}"
        undo_activity = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": f"{base}/users/{config.USERNAME}/activities/undo-follow-{int(time.time())}",
            "type": "Undo",
            "actor": f"{base}/users/{config.USERNAME}",
            "object": {
                "type": "Follow",
                "actor": f"{base}/users/{config.USERNAME}",
                "object": ra.uri,
            },
        }
        deliver_to_inbox(ra.inbox_url, undo_activity)

    is_followed_by = Follower.query.filter_by(
        remote_account_id=ra.id, approved=True
    ).first() is not None
    return jsonify(
        serialize_relationship(
            ra.id,
            is_following=False,
            is_followed_by=is_followed_by,
        )
    )


@api_accounts_bp.route("/api/v1/accounts/<account_id>/block", methods=["POST"])
@require_auth
def block_account(account_id):
    aid = _parse_int(account_id)
    if aid is None:
        return jsonify({"error": "Record not found"}), 404
    ra = db.session.get(RemoteAccount, aid)
    if not ra:
        return jsonify({"error": "Record not found"}), 404
    existing = Block.query.filter_by(remote_account_id=ra.id).first()
    if not existing:
        block = Block(remote_account_id=ra.id)
        db.session.add(block)
        # Also unfollow and remove follower
        Following.query.filter_by(remote_account_id=ra.id).delete()
        Follower.query.filter_by(remote_account_id=ra.id).delete()
        db.session.commit()
    return jsonify(serialize_relationship(ra.id, is_blocking=True))


@api_accounts_bp.route("/api/v1/accounts/<account_id>/unblock", methods=["POST"])
@require_auth
def unblock_account(account_id):
    aid = _parse_int(account_id)
    if aid is None:
        return jsonify({"error": "Record not found"}), 404
    ra = db.session.get(RemoteAccount, aid)
    if not ra:
        return jsonify({"error": "Record not found"}), 404
    Block.query.filter_by(remote_account_id=ra.id).delete()
    db.session.commit()
    return jsonify(serialize_relationship(ra.id))


@api_accounts_bp.route("/api/v1/accounts/<account_id>/mute", methods=["POST"])
@require_auth
def mute_account(account_id):
    aid = _parse_int(account_id)
    if aid is None:
        return jsonify({"error": "Record not found"}), 404
    ra = db.session.get(RemoteAccount, aid)
    if not ra:
        return jsonify({"error": "Record not found"}), 404
    existing = Mute.query.filter_by(remote_account_id=ra.id).first()
    if not existing:
        mute = Mute(remote_account_id=ra.id)
        db.session.add(mute)
        db.session.commit()
    is_following = Following.query.filter_by(
        remote_account_id=ra.id, approved=True
    ).first() is not None
    return jsonify(serialize_relationship(ra.id, is_following=is_following, is_muting=True))


@api_accounts_bp.route("/api/v1/accounts/<account_id>/unmute", methods=["POST"])
@require_auth
def unmute_account(account_id):
    aid = _parse_int(account_id)
    if aid is None:
        return jsonify({"error": "Record not found"}), 404
    ra = db.session.get(RemoteAccount, aid)
    if not ra:
        return jsonify({"error": "Record not found"}), 404
    Mute.query.filter_by(remote_account_id=ra.id).delete()
    db.session.commit()
    is_following = Following.query.filter_by(
        remote_account_id=ra.id, approved=True
    ).first() is not None
    return jsonify(serialize_relationship(ra.id, is_following=is_following))


@api_accounts_bp.route("/api/v1/follow_requests", methods=["GET"])
@require_auth
def follow_requests():
    pending = Follower.query.filter_by(approved=False).all()
    return jsonify(
        [serialize_remote_account(f.remote_account) for f in pending if f.remote_account]
    )


@api_accounts_bp.route(
    "/api/v1/follow_requests/<int:req_id>/authorize", methods=["POST"]
)
@require_auth
def authorize_follow(req_id):
    follower = db.session.get(Follower, req_id)
    if follower:
        follower.approved = True
        db.session.commit()
    return "{}", 200


@api_accounts_bp.route(
    "/api/v1/follow_requests/<int:req_id>/reject", methods=["POST"]
)
@require_auth
def reject_follow(req_id):
    follower = db.session.get(Follower, req_id)
    if follower:
        db.session.delete(follower)
        db.session.commit()
    return "{}", 200


@api_accounts_bp.route("/api/v1/preferences", methods=["GET"])
@require_auth
def preferences():
    return jsonify(
        {
            "posting:default:visibility": "public",
            "posting:default:sensitive": False,
            "posting:default:language": "en",
            "reading:expand:media": "default",
            "reading:expand:spoilers": False,
        }
    )


def _add_pagination_headers(response, items, path):
    """Add Link headers for pagination."""
    if not items:
        return
    base = f"https://{config.DOMAIN}"
    links = []
    links.append(f'<{base}{path}?max_id={items[-1].id}>; rel="next"')
    links.append(f'<{base}{path}?min_id={items[0].id}>; rel="prev"')
    response.headers["Link"] = ", ".join(links)
