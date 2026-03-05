"""
Mastodon API: Timeline endpoints.
"""

from flask import Blueprint, request, jsonify
import config
from models import Status, Following, Mute, Block
from utils.auth import require_auth, optional_auth
from utils.serializers import serialize_status

api_timelines_bp = Blueprint("api_timelines", __name__)


def _parse_int(value, default=None):
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _paginate_statuses(query, req):
    """Apply common pagination parameters to a status query."""
    limit = min(_parse_int(req.args.get("limit"), 20), 40)
    max_id = _parse_int(req.args.get("max_id"))
    min_id = _parse_int(req.args.get("min_id"))
    since_id = _parse_int(req.args.get("since_id"))

    if max_id is not None:
        query = query.filter(Status.id < max_id)
    if min_id is not None:
        query = query.filter(Status.id > min_id)
    if since_id is not None:
        query = query.filter(Status.id > since_id)

    return query.order_by(Status.id.desc()).limit(limit)


def _add_link_headers(response, statuses, path):
    """Add Link headers for Mastodon pagination."""
    if not statuses:
        return response
    base = f"https://{config.DOMAIN}"
    links = [
        f'<{base}{path}?max_id={statuses[-1].id}>; rel="next"',
        f'<{base}{path}?min_id={statuses[0].id}>; rel="prev"',
    ]
    response.headers["Link"] = ", ".join(links)
    return response


def _blocked_account_ids():
    """Get IDs of blocked/muted remote accounts."""
    blocked = {b.remote_account_id for b in Block.query.all()}
    muted = {m.remote_account_id for m in Mute.query.all()}
    return blocked | muted


@api_timelines_bp.route("/api/v1/timelines/home", methods=["GET"])
@require_auth
def timeline_home():
    """Home timeline: own posts + posts from followed accounts."""
    blocked = _blocked_account_ids()

    # Get IDs of accounts we follow
    following_ids = {
        f.remote_account_id
        for f in Following.query.filter_by(approved=True).all()
    }

    query = Status.query.filter(
        Status.deleted_at.is_(None),
        Status.reblog_of_id.is_(None) | (Status.remote == False),
    ).filter(
        # Our own posts OR posts from followed accounts
        (Status.remote == False)
        | (
            (Status.remote == True)
            & (Status.remote_account_id.in_(following_ids))
        )
    )

    # Exclude blocked accounts
    if blocked:
        query = query.filter(
            (Status.remote_account_id.notin_(blocked)) | (Status.remote == False)
        )

    statuses = _paginate_statuses(query, request).all()
    result = [serialize_status(s, for_account="local") for s in statuses]

    response = jsonify(result)
    return _add_link_headers(response, statuses, "/api/v1/timelines/home")


@api_timelines_bp.route("/api/v1/timelines/public", methods=["GET"])
@optional_auth
def timeline_public():
    """Public (federated or local) timeline."""
    local = request.args.get("local") == "true"
    only_media = request.args.get("only_media") == "true"
    blocked = _blocked_account_ids()

    query = Status.query.filter(
        Status.deleted_at.is_(None),
        Status.visibility == "public",
        Status.reblog_of_id.is_(None),
    )

    if local:
        query = query.filter(Status.remote == False)

    if blocked:
        query = query.filter(
            (Status.remote_account_id.notin_(blocked)) | (Status.remote == False)
        )

    statuses = _paginate_statuses(query, request).all()

    if only_media:
        statuses = [s for s in statuses if s.media_attachments]

    account = "local" if request.oauth_token else None
    result = [serialize_status(s, for_account=account) for s in statuses]

    response = jsonify(result)
    return _add_link_headers(response, statuses, "/api/v1/timelines/public")


@api_timelines_bp.route("/api/v1/timelines/tag/<tag>", methods=["GET"])
@optional_auth
def timeline_tag(tag):
    """Hashtag timeline — search content for the tag."""
    tag_lower = tag.lower()
    query = Status.query.filter(
        Status.deleted_at.is_(None),
        Status.visibility == "public",
        Status.content.ilike(f"%#{tag_lower}%"),
    )

    statuses = _paginate_statuses(query, request).all()
    account = "local" if request.oauth_token else None
    result = [serialize_status(s, for_account=account) for s in statuses]

    response = jsonify(result)
    return _add_link_headers(response, statuses, f"/api/v1/timelines/tag/{tag}")


@api_timelines_bp.route("/api/v1/timelines/list/<list_id>", methods=["GET"])
@require_auth
def timeline_list(list_id):
    """List timeline — not implemented, return empty."""
    return jsonify([])
