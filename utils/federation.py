"""
ActivityPub federation helpers – sending activities to remote servers.
"""

import json
import logging
import requests

import config
from utils.crypto import sign_headers

logger = logging.getLogger(__name__)


def deliver_to_inbox(inbox_url, activity):
    """Sign and POST an activity to a remote inbox."""
    body = json.dumps(activity).encode("utf-8")
    content_type = "application/activity+json"
    headers = sign_headers("POST", inbox_url, body=body, content_type=content_type)
    headers["Content-Type"] = content_type
    headers["User-Agent"] = f"Actimish/{config.SOFTWARE_VERSION}"
    try:
        resp = requests.post(inbox_url, data=body, headers=headers, timeout=15)
        logger.info("Delivered to %s → %s", inbox_url, resp.status_code)
        return resp.status_code
    except Exception as e:
        logger.error("Failed to deliver to %s: %s", inbox_url, e)
        return None


def deliver_to_followers(activity):
    """Deliver an activity to all follower inboxes (de-duplicated by shared inbox)."""
    from models import Follower

    followers = Follower.query.filter_by(approved=True).all()
    seen_inboxes = set()
    for f in followers:
        ra = f.remote_account
        inbox = ra.shared_inbox_url or ra.inbox_url
        if inbox and inbox not in seen_inboxes:
            seen_inboxes.add(inbox)
            deliver_to_inbox(inbox, activity)


def fetch_remote_actor(actor_uri):
    """Fetch and cache a remote actor. Returns a RemoteAccount or None."""
    from models import db, RemoteAccount

    existing = RemoteAccount.query.filter_by(uri=actor_uri).first()
    if existing:
        return existing

    try:
        resp = requests.get(
            actor_uri,
            headers={
                "Accept": "application/activity+json",
                "User-Agent": f"Actimish/{config.SOFTWARE_VERSION}",
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error("Failed to fetch actor %s: %s", actor_uri, e)
        return None

    from urllib.parse import urlparse
    domain = urlparse(actor_uri).hostname

    ra = RemoteAccount(
        uri=actor_uri,
        url=data.get("url", actor_uri),
        username=data.get("preferredUsername", "unknown"),
        domain=domain,
        display_name=data.get("name", ""),
        avatar_url=(data.get("icon") or {}).get("url", ""),
        header_url=(data.get("image") or {}).get("url", ""),
        bio=data.get("summary", ""),
        inbox_url=data.get("inbox", ""),
        shared_inbox_url=(data.get("endpoints") or {}).get("sharedInbox", ""),
        outbox_url=data.get("outbox", ""),
        public_key_pem=(data.get("publicKey") or {}).get("publicKeyPem", ""),
        followers_url=data.get("followers", ""),
        following_url=data.get("following", ""),
    )
    db.session.add(ra)
    db.session.commit()
    return ra


def build_actor_object():
    """Build the ActivityPub Actor JSON for the local user."""
    base = f"https://{config.DOMAIN}"
    actor_url = f"{base}/users/{config.USERNAME}"
    from utils.crypto import get_public_key_pem

    return {
        "@context": [
            "https://www.w3.org/ns/activitystreams",
            "https://w3id.org/security/v1",
        ],
        "id": actor_url,
        "type": "Person",
        "preferredUsername": config.USERNAME,
        "name": config.DISPLAY_NAME,
        "summary": config.BIO or "",
        "url": f"{base}/@{config.USERNAME}",
        "inbox": f"{actor_url}/inbox",
        "outbox": f"{actor_url}/outbox",
        "followers": f"{actor_url}/followers",
        "following": f"{actor_url}/following",
        "manuallyApprovesFollowers": False,
        "discoverable": True,
        "published": "2026-01-01T00:00:00Z",
        "icon": {
            "type": "Image",
            "mediaType": _get_avatar_mime_type(),
            "url": _get_avatar_url(base),
        },
        "image": {
            "type": "Image",
            "mediaType": _get_header_mime_type(),
            "url": _get_header_url(base),
        },
        "endpoints": {
            "sharedInbox": f"{base}/inbox",
        },
        "publicKey": {
            "id": f"{actor_url}#main-key",
            "owner": actor_url,
            "publicKeyPem": get_public_key_pem(),
        },
    }


def build_note_object(status):
    """Build an ActivityPub Note from a Status model."""
    base = f"https://{config.DOMAIN}"
    actor_url = f"{base}/users/{config.USERNAME}"
    note_url = f"{base}/users/{config.USERNAME}/statuses/{status.id}"

    to = []
    cc = []
    if status.visibility == "public":
        to = ["https://www.w3.org/ns/activitystreams#Public"]
        cc = [f"{actor_url}/followers"]
    elif status.visibility == "unlisted":
        to = [f"{actor_url}/followers"]
        cc = ["https://www.w3.org/ns/activitystreams#Public"]
    elif status.visibility == "private":
        to = [f"{actor_url}/followers"]
    # direct: to specific mentioned users (not implemented yet)

    attachments = []
    for m in status.media_attachments:
        att = {
            "type": "Document",
            "mediaType": m.mime_type,
            "url": f"{base}/media/{m.file_path}",
        }
        if m.description:
            att["name"] = m.description
        if m.width and m.height:
            att["width"] = m.width
            att["height"] = m.height
        if m.focus_x is not None and m.focus_y is not None:
            att["focalPoint"] = [m.focus_x, m.focus_y]
        attachments.append(att)

    note = {
        "@context": "https://www.w3.org/ns/activitystreams",
        "id": note_url,
        "type": "Note",
        "attributedTo": actor_url,
        "content": status.content,
        "published": _epoch_to_w3c(status.created_at),
        "to": to,
        "cc": cc,
        "url": f"{base}/@{config.USERNAME}/{status.id}",
        "sensitive": status.sensitive,
        "summary": status.spoiler_text or None,
    }
    if status.in_reply_to_uri:
        note["inReplyTo"] = status.in_reply_to_uri
    if attachments:
        note["attachment"] = attachments
    if status.language:
        note["contentMap"] = {status.language: status.content}

    return note


def _get_avatar_mime_type():
    """Get the MIME type of the current avatar."""
    import os
    from utils.settings import get_setting
    
    # Check settings first
    mime = get_setting("avatar_mime")
    if mime:
        return mime
    
    # Fall back to checking what file exists
    for ext in ["png", "jpg", "jpeg", "gif", "webp"]:
        path = os.path.join(config.DATA_DIR, f"avatar.{ext}")
        if os.path.isfile(path):
            ext_mime_map = {
                "png": "image/png",
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg",
                "gif": "image/gif",
                "webp": "image/webp",
            }
            return ext_mime_map.get(ext, "image/png")
    
    return "image/png"


def _get_avatar_url(base):
    """Get the full URL to the current avatar."""
    import os
    
    # Check what avatar file exists
    for ext in ["png", "jpg", "jpeg", "gif", "webp"]:
        path = os.path.join(config.DATA_DIR, f"avatar.{ext}")
        if os.path.isfile(path):
            return f"{base}/avatar.{ext}"
    
    return f"{base}/avatar.png"


def _get_header_mime_type():
    """Get the MIME type of the current header."""
    import os
    from utils.settings import get_setting
    
    # Check settings first
    mime = get_setting("header_mime")
    if mime:
        return mime
    
    # Fall back to checking what file exists
    for ext in ["png", "jpg", "jpeg", "gif", "webp"]:
        path = os.path.join(config.DATA_DIR, f"header.{ext}")
        if os.path.isfile(path):
            ext_mime_map = {
                "png": "image/png",
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg",
                "gif": "image/gif",
                "webp": "image/webp",
            }
            return ext_mime_map.get(ext, "image/png")
    
    return "image/png"


def _get_header_url(base):
    """Get the full URL to the current header."""
    import os
    
    # Check what header file exists
    for ext in ["png", "jpg", "jpeg", "gif", "webp"]:
        path = os.path.join(config.DATA_DIR, f"header.{ext}")
        if os.path.isfile(path):
            return f"{base}/header.{ext}"
    
    return f"{base}/header.png"


def _epoch_to_w3c(epoch):
    import datetime
    dt = datetime.datetime.fromtimestamp(epoch, tz=datetime.timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
