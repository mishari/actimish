"""
.well-known endpoints: WebFinger, NodeInfo, host-meta.
"""

from flask import Blueprint, request, jsonify, Response
import config

wellknown_bp = Blueprint("wellknown", __name__)


@wellknown_bp.route("/.well-known/webfinger")
def webfinger():
    resource = request.args.get("resource", "")
    expected = f"acct:{config.USERNAME}@{config.DOMAIN}"
    if resource != expected:
        return jsonify({"error": "Resource not found"}), 404

    base = f"https://{config.DOMAIN}"
    data = {
        "subject": expected,
        "aliases": [
            f"{base}/@{config.USERNAME}",
            f"{base}/users/{config.USERNAME}",
        ],
        "links": [
            {
                "rel": "http://webfinger.net/rel/profile-page",
                "type": "text/html",
                "href": f"{base}/@{config.USERNAME}",
            },
            {
                "rel": "self",
                "type": "application/activity+json",
                "href": f"{base}/users/{config.USERNAME}",
            },
            {
                "rel": "http://ostatus.org/schema/1.0/subscribe",
                "template": f"{base}/authorize_interaction?uri={{uri}}",
            },
        ],
    }
    return Response(
        response=__import__("json").dumps(data),
        status=200,
        content_type="application/jrd+json; charset=utf-8",
    )


@wellknown_bp.route("/.well-known/nodeinfo")
def nodeinfo_wellknown():
    base = f"https://{config.DOMAIN}"
    return jsonify(
        {
            "links": [
                {
                    "rel": "http://nodeinfo.diaspora.software/ns/schema/2.0",
                    "href": f"{base}/nodeinfo/2.0",
                }
            ]
        }
    )


@wellknown_bp.route("/nodeinfo/2.0")
def nodeinfo():
    from models import Status, Follower

    local_posts = Status.query.filter_by(remote=False, deleted_at=None).count()
    return jsonify(
        {
            "version": "2.0",
            "software": {
                "name": config.SOFTWARE_NAME,
                "version": config.SOFTWARE_VERSION,
            },
            "protocols": ["activitypub"],
            "usage": {
                "users": {"total": 1, "activeMonth": 1, "activeHalfyear": 1},
                "localPosts": local_posts,
            },
            "openRegistrations": False,
        }
    )


@wellknown_bp.route("/.well-known/host-meta")
def host_meta():
    base = f"https://{config.DOMAIN}"
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<XRD xmlns="http://docs.oasis-open.org/ns/xri/xrd-1.0">
  <Link rel="lrdd" template="{base}/.well-known/webfinger?resource={{uri}}" type="application/jrd+json"/>
</XRD>"""
    return Response(xml, content_type="application/xrd+xml; charset=utf-8")
