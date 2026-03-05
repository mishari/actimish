"""
Serialize database models to Mastodon API JSON responses.
"""

import html
import re

import config
from models import (
    Status,
    MediaAttachment,
    RemoteAccount,
    Favourite,
    Bookmark,
    Notification,
)


def _plaintext_from_html(value):
    if not value:
        return ""
    text = value
    text = re.sub(r"<\s*br\s*/?\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</\s*p\s*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    # Normalize whitespace while preserving newlines.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_mentions_and_tags(status_content):
    text = _plaintext_from_html(status_content)

    mentions = []
    seen_accts = set()

    mention_re = re.compile(
        r"(?<![A-Za-z0-9_])@([A-Za-z0-9_]+)(?:@([A-Za-z0-9.-]+))?"
    )
    for m in mention_re.finditer(text):
        username = m.group(1)
        domain = m.group(2)

        if domain:
            acct = f"{username}@{domain}"
        else:
            acct = username

        acct_lower = acct.lower()
        if acct_lower in seen_accts:
            continue
        seen_accts.add(acct_lower)

        if (not domain and username == config.USERNAME) or (
            domain and username == config.USERNAME and domain == config.DOMAIN
        ):
            mentions.append(
                {
                    "id": "1",
                    "username": config.USERNAME,
                    "acct": config.USERNAME,
                    "url": f"{_base_url()}/@{config.USERNAME}",
                }
            )
            continue

        ra = None
        if domain:
            ra = RemoteAccount.query.filter_by(
                username=username, domain=domain
            ).first()

        if ra:
            mentions.append(
                {
                    "id": str(ra.id),
                    "username": ra.username,
                    "acct": f"{ra.username}@{ra.domain}",
                    "url": ra.url or ra.uri or "",
                }
            )
        else:
            url = ""
            if domain:
                url = f"https://{domain}/@{username}"
            mentions.append(
                {
                    "id": acct,
                    "username": username,
                    "acct": acct,
                    "url": url,
                }
            )

    tags = []
    seen_tags = set()
    tag_re = re.compile(r"(?<![A-Za-z0-9_])#([A-Za-z0-9_]+)")
    for m in tag_re.finditer(text):
        name = m.group(1).lower()
        if name in seen_tags:
            continue
        seen_tags.add(name)
        tags.append({"name": name, "url": f"{_base_url()}/tags/{name}"})

    return mentions, tags


def _base_url():
    return f"https://{config.DOMAIN}"


def serialize_account_local():
    """Serialize the single local user account."""
    import os
    from utils.settings import get_setting
    
    followers_count = 0
    following_count = 0
    statuses_count = 0
    try:
        from models import Follower, Following, Status as StatusModel

        followers_count = Follower.query.filter_by(approved=True).count()
        following_count = Following.query.filter_by(approved=True).count()
        statuses_count = StatusModel.query.filter_by(remote=False, deleted_at=None).count()
    except Exception:
        # During early startup / migrations, DB may not be ready.
        pass

    # Determine avatar and header URLs based on what files exist
    base_url = _base_url()
    avatar_url = f"{base_url}/avatar.png"
    header_url = f"{base_url}/header.png"
    
    # Check for actual avatar/header files with different extensions
    try:
        for ext in ["png", "jpg", "jpeg", "gif", "webp"]:
            avatar_path = os.path.join(config.DATA_DIR, f"avatar.{ext}")
            if os.path.exists(avatar_path):
                avatar_url = f"{base_url}/avatar.{ext}"
                break
        
        for ext in ["png", "jpg", "jpeg", "gif", "webp"]:
            header_path = os.path.join(config.DATA_DIR, f"header.{ext}")
            if os.path.exists(header_path):
                header_url = f"{base_url}/header.{ext}"
                break
    except Exception:
        # If any error, fall back to defaults
        pass

    return {
        "id": "1",
        "username": config.USERNAME,
        "acct": config.USERNAME,
        "display_name": config.DISPLAY_NAME,
        "locked": False,
        "bot": False,
        "discoverable": True,
        "group": False,
        "created_at": "2026-01-01T00:00:00.000Z",
        "note": config.BIO or "",
        "url": f"{_base_url()}/@{config.USERNAME}",
        "uri": f"{_base_url()}/users/{config.USERNAME}",
        "avatar": avatar_url,
        "avatar_static": avatar_url,
        "header": header_url,
        "header_static": header_url,
        "followers_count": followers_count,
        "following_count": following_count,
        "statuses_count": statuses_count,
        "last_status_at": None,
        "noindex": False,
        "emojis": [],
        "roles": [],
        "fields": [],
    }


def serialize_credential_account():
    """Serialize the local user for verify_credentials (includes source)."""
    from models import Follower, Following, Status as StatusModel

    acct = serialize_account_local()
    acct["followers_count"] = Follower.query.filter_by(approved=True).count()
    acct["following_count"] = Following.query.filter_by(approved=True).count()
    acct["statuses_count"] = StatusModel.query.filter_by(
        remote=False, deleted_at=None
    ).count()
    acct["source"] = {
        "privacy": "public",
        "sensitive": False,
        "language": "en",
        "note": config.BIO or "",
        "fields": [],
        "follow_requests_count": Follower.query.filter_by(approved=False).count(),
    }
    return acct


def serialize_remote_account(ra: RemoteAccount):
    """Serialize a remote account."""
    return {
        "id": str(ra.id),
        "username": ra.username,
        "acct": f"{ra.username}@{ra.domain}",
        "display_name": ra.display_name or ra.username,
        "locked": False,
        "bot": False,
        "discoverable": False,
        "group": False,
        "created_at": _epoch_to_iso(ra.created_at),
        "note": ra.bio or "",
        "url": ra.url or ra.uri,
        "uri": ra.uri,
        "avatar": ra.avatar_url or "",
        "avatar_static": ra.avatar_url or "",
        "header": ra.header_url or "",
        "header_static": ra.header_url or "",
        "followers_count": 0,
        "following_count": 0,
        "statuses_count": 0,
        "last_status_at": None,
        "noindex": False,
        "emojis": [],
        "roles": [],
        "fields": [],
    }


def serialize_media(m: MediaAttachment):
    """Serialize a media attachment."""
    base = _base_url()
    url = f"{base}/media/{m.file_path}" if m.file_path else None
    preview = f"{base}/media/{m.thumbnail_path}" if m.thumbnail_path else url
    meta = {}
    if m.width and m.height:
        meta["original"] = {
            "width": m.width,
            "height": m.height,
            "size": f"{m.width}x{m.height}",
            "aspect": round(m.width / m.height, 6) if m.height else 1.0,
        }
        meta["small"] = meta["original"]
    if m.focus_x is not None and m.focus_y is not None:
        meta["focus"] = {"x": m.focus_x, "y": m.focus_y}
    return {
        "id": str(m.id),
        "type": m.media_type,
        "url": url if not m.processing else None,
        "preview_url": preview if not m.processing else None,
        "remote_url": None,
        "preview_remote_url": None,
        "text_url": None,
        "meta": meta,
        "description": m.description or None,
        "blurhash": None,
    }


def serialize_status(s: Status, for_account=None):
    """Serialize a status for the Mastodon API."""
    if s.remote and s.remote_account:
        account = serialize_remote_account(s.remote_account)
    else:
        account = serialize_account_local()

    media = [serialize_media(m) for m in s.media_attachments]

    reblog = None
    if s.reblog_of_id and s.reblog:
        reblog = serialize_status(s.reblog)

    # Check interaction state for authenticated user
    favourited = False
    bookmarked = False
    reblogged = False
    if for_account == "local":
        favourited = Favourite.query.filter_by(
            status_id=s.id, local=True
        ).first() is not None
        bookmarked = Bookmark.query.filter_by(status_id=s.id).first() is not None
        reblogged = Status.query.filter_by(
            reblog_of_id=s.id, remote=False, deleted_at=None
        ).first() is not None

    mentions, tags = _extract_mentions_and_tags(s.content)

    return {
        "id": str(s.id),
        "created_at": _epoch_to_iso(s.created_at),
        "in_reply_to_id": str(s.in_reply_to_id) if s.in_reply_to_id else None,
        "in_reply_to_account_id": None,
        "sensitive": s.sensitive,
        "spoiler_text": s.spoiler_text or "",
        "visibility": s.visibility,
        "language": s.language or "en",
        "uri": s.uri,
        "url": s.remote_url or f"{_base_url()}/@{config.USERNAME}/{s.id}",
        "replies_count": s.replies_count,
        "reblogs_count": s.reblogs_count,
        "favourites_count": s.favourites_count,
        "edited_at": _epoch_to_iso(s.updated_at) if s.updated_at != s.created_at else None,
        "favourited": favourited,
        "reblogged": reblogged,
        "muted": False,
        "bookmarked": bookmarked,
        "pinned": s.pinned if not s.remote else False,
        "text": None,
        "content": s.content,
        "reblog": reblog,
        "application": {"name": "Actimish", "website": None},
        "account": account,
        "media_attachments": media,
        "mentions": mentions,
        "tags": tags,
        "emojis": [],
        "card": None,
        "poll": None,
        "filtered": [],
    }


def serialize_notification(n: Notification):
    """Serialize a notification."""
    result = {
        "id": str(n.id),
        "type": n.type,
        "created_at": _epoch_to_iso(n.created_at),
        "account": serialize_remote_account(n.remote_account) if n.remote_account else serialize_account_local(),
    }
    if n.status:
        result["status"] = serialize_status(n.status)
    return result


def serialize_relationship(remote_account_id, is_following=False, is_followed_by=False,
                           is_blocking=False, is_muting=False):
    """Serialize a relationship object."""
    return {
        "id": str(remote_account_id),
        "following": is_following,
        "showing_reblogs": True,
        "notifying": False,
        "languages": [],
        "followed_by": is_followed_by,
        "blocking": is_blocking,
        "blocked_by": False,
        "muting": is_muting,
        "muting_notifications": is_muting,
        "requested": False,
        "requested_by": False,
        "domain_blocking": False,
        "endorsed": False,
        "note": "",
    }


def _epoch_to_iso(epoch):
    """Convert epoch seconds to ISO 8601 string."""
    if epoch is None:
        return None
    import datetime
    dt = datetime.datetime.fromtimestamp(epoch, tz=datetime.timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
