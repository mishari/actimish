"""
Mastodon API: Search endpoint.
"""

from flask import Blueprint, request, jsonify
import config
from models import Status, RemoteAccount
from utils.auth import optional_auth
from utils.serializers import (
    serialize_status,
    serialize_account_local,
    serialize_remote_account,
)

api_search_bp = Blueprint("api_search", __name__)


def _parse_int(value, default=None):
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


@api_search_bp.route("/api/v2/search", methods=["GET"])
@optional_auth
def search():
    q = request.args.get("q", "").strip()
    search_type = request.args.get("type")
    limit = min(_parse_int(request.args.get("limit"), 20), 40)
    resolve = request.args.get("resolve") == "true"

    accounts = []
    statuses = []
    hashtags = []

    if not q:
        return jsonify({"accounts": [], "statuses": [], "hashtags": []})

    account = "local" if request.oauth_token else None

    # Search accounts
    if not search_type or search_type == "accounts":
        # Check local user
        if config.USERNAME.lower().startswith(q.lower()) or config.DISPLAY_NAME.lower().startswith(q.lower()):
            accounts.append(serialize_account_local())

        # Search remote accounts
        remote = (
            RemoteAccount.query.filter(
                (RemoteAccount.username.ilike(f"%{q}%"))
                | (RemoteAccount.display_name.ilike(f"%{q}%"))
            )
            .limit(limit)
            .all()
        )
        for ra in remote:
            accounts.append(serialize_remote_account(ra))

        # Try to resolve remote account via WebFinger
        if resolve and "@" in q and not remote:
            _try_resolve_account(q, accounts)

    # Search statuses
    if not search_type or search_type == "statuses":
        query = Status.query.filter(
            Status.deleted_at.is_(None),
            Status.content.ilike(f"%{q}%"),
        )
        if not request.oauth_token:
            query = query.filter(Status.visibility.in_(["public", "unlisted"]))
        results = query.order_by(Status.id.desc()).limit(limit).all()
        statuses = [serialize_status(s, for_account=account) for s in results]

    # Search hashtags
    if not search_type or search_type == "hashtags":
        if q.startswith("#"):
            q_tag = q[1:]
        else:
            q_tag = q
        # Find tags in status content
        tag_statuses = (
            Status.query.filter(
                Status.deleted_at.is_(None),
                Status.content.ilike(f"%#{q_tag}%"),
            )
            .limit(5)
            .all()
        )
        if tag_statuses:
            hashtags.append(
                {
                    "name": q_tag.lower(),
                    "url": f"https://{config.DOMAIN}/tags/{q_tag.lower()}",
                    "history": [],
                    "following": False,
                }
            )

    return jsonify(
        {
            "accounts": accounts[:limit],
            "statuses": statuses[:limit],
            "hashtags": hashtags[:limit],
        }
    )


def _try_resolve_account(acct, accounts_list):
    """Try to resolve a remote account via WebFinger."""
    import requests
    from utils.federation import fetch_remote_actor

    # Clean the acct
    if acct.startswith("@"):
        acct = acct[1:]
    parts = acct.split("@")
    if len(parts) != 2:
        return
    username, domain = parts

    try:
        wf_url = f"https://{domain}/.well-known/webfinger?resource=acct:{acct}"
        resp = requests.get(wf_url, timeout=10)
        resp.raise_for_status()
        wf_data = resp.json()

        # Find the self link
        actor_url = None
        for link in wf_data.get("links", []):
            if link.get("rel") == "self" and "activity+json" in link.get("type", ""):
                actor_url = link["href"]
                break

        if actor_url:
            ra = fetch_remote_actor(actor_url)
            if ra:
                accounts_list.append(serialize_remote_account(ra))
    except Exception:
        pass
