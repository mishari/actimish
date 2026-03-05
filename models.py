"""
Database models for Actimish – single-user ActivityPub server.
"""

import time
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def _now():
    """Current time as integer epoch seconds."""
    return int(time.time())


# ── OAuth models ──────────────────────────────────────────────────


class OAuthApp(db.Model):
    """Registered OAuth client applications (e.g. Tusky)."""

    __tablename__ = "oauth_apps"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    client_secret = db.Column(db.String(64), nullable=False)
    client_name = db.Column(db.String(256), nullable=False)
    redirect_uris = db.Column(db.Text, nullable=False)  # space-separated
    scopes = db.Column(db.String(256), default="read")
    website = db.Column(db.String(512))
    created_at = db.Column(db.Integer, default=_now)


class OAuthToken(db.Model):
    """Issued access tokens."""

    __tablename__ = "oauth_tokens"

    id = db.Column(db.Integer, primary_key=True)
    access_token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    token_type = db.Column(db.String(16), default="Bearer")
    scope = db.Column(db.String(256), default="read")
    app_id = db.Column(db.Integer, db.ForeignKey("oauth_apps.id"), nullable=False)
    created_at = db.Column(db.Integer, default=_now)
    revoked = db.Column(db.Boolean, default=False)

    app = db.relationship("OAuthApp", backref="tokens")


class OAuthAuthCode(db.Model):
    """Temporary authorization codes exchanged for tokens."""

    __tablename__ = "oauth_auth_codes"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), unique=True, nullable=False, index=True)
    app_id = db.Column(db.Integer, db.ForeignKey("oauth_apps.id"), nullable=False)
    redirect_uri = db.Column(db.Text, nullable=False)
    scope = db.Column(db.String(256), default="read")
    created_at = db.Column(db.Integer, default=_now)
    used = db.Column(db.Boolean, default=False)

    app = db.relationship("OAuthApp")


# ── Status / Post ────────────────────────────────────────────────


class Status(db.Model):
    """A post / note."""

    __tablename__ = "statuses"

    id = db.Column(db.Integer, primary_key=True)
    uri = db.Column(db.String(512), unique=True, nullable=False, index=True)
    content = db.Column(db.Text, nullable=False, default="")
    content_type = db.Column(db.String(32), default="text/html")
    spoiler_text = db.Column(db.Text, default="")
    visibility = db.Column(db.String(16), default="public")  # public|unlisted|private|direct
    sensitive = db.Column(db.Boolean, default=False)
    language = db.Column(db.String(8))
    in_reply_to_id = db.Column(db.Integer, db.ForeignKey("statuses.id"))
    in_reply_to_uri = db.Column(db.String(512))
    reblog_of_id = db.Column(db.Integer, db.ForeignKey("statuses.id"))

    # Remote statuses
    remote = db.Column(db.Boolean, default=False)
    remote_account_id = db.Column(db.Integer, db.ForeignKey("remote_accounts.id"))
    remote_url = db.Column(db.String(512))

    favourites_count = db.Column(db.Integer, default=0)
    reblogs_count = db.Column(db.Integer, default=0)
    replies_count = db.Column(db.Integer, default=0)

    pinned = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.Integer, default=_now)
    updated_at = db.Column(db.Integer, default=_now, onupdate=_now)
    deleted_at = db.Column(db.Integer)

    # Relationships
    media_attachments = db.relationship("MediaAttachment", backref="status", lazy="select")
    reblog = db.relationship("Status", remote_side=[id], foreign_keys=[reblog_of_id])
    reply_to = db.relationship("Status", remote_side=[id], foreign_keys=[in_reply_to_id])
    remote_account = db.relationship("RemoteAccount", backref="statuses")


# ── Media ─────────────────────────────────────────────────────────


class MediaAttachment(db.Model):
    """Uploaded images and videos."""

    __tablename__ = "media_attachments"

    id = db.Column(db.Integer, primary_key=True)
    status_id = db.Column(db.Integer, db.ForeignKey("statuses.id"))
    file_path = db.Column(db.String(512), nullable=False)
    thumbnail_path = db.Column(db.String(512))
    media_type = db.Column(db.String(32), nullable=False)  # image or video
    mime_type = db.Column(db.String(64), nullable=False)
    description = db.Column(db.Text, default="")
    focus_x = db.Column(db.Float, default=0.0)
    focus_y = db.Column(db.Float, default=0.0)
    width = db.Column(db.Integer)
    height = db.Column(db.Integer)
    size = db.Column(db.Integer)  # bytes
    processing = db.Column(db.Boolean, default=False)  # True while async processing
    created_at = db.Column(db.Integer, default=_now)


# ── Remote accounts ──────────────────────────────────────────────


class RemoteAccount(db.Model):
    """Cached remote ActivityPub actors."""

    __tablename__ = "remote_accounts"

    id = db.Column(db.Integer, primary_key=True)
    uri = db.Column(db.String(512), unique=True, nullable=False, index=True)
    url = db.Column(db.String(512))
    username = db.Column(db.String(256), nullable=False)
    domain = db.Column(db.String(256), nullable=False)
    display_name = db.Column(db.String(512), default="")
    avatar_url = db.Column(db.String(512))
    header_url = db.Column(db.String(512))
    bio = db.Column(db.Text, default="")
    inbox_url = db.Column(db.String(512), nullable=False)
    shared_inbox_url = db.Column(db.String(512))
    outbox_url = db.Column(db.String(512))
    public_key_pem = db.Column(db.Text)
    followers_url = db.Column(db.String(512))
    following_url = db.Column(db.String(512))
    created_at = db.Column(db.Integer, default=_now)
    updated_at = db.Column(db.Integer, default=_now, onupdate=_now)


# ── Followers / Following ────────────────────────────────────────


class Follower(db.Model):
    """Accounts that follow the local user."""

    __tablename__ = "followers"

    id = db.Column(db.Integer, primary_key=True)
    remote_account_id = db.Column(
        db.Integer, db.ForeignKey("remote_accounts.id"), nullable=False
    )
    approved = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.Integer, default=_now)

    remote_account = db.relationship("RemoteAccount", backref="follower_records")


class Following(db.Model):
    """Accounts the local user follows."""

    __tablename__ = "following"

    id = db.Column(db.Integer, primary_key=True)
    remote_account_id = db.Column(
        db.Integer, db.ForeignKey("remote_accounts.id"), nullable=False
    )
    approved = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.Integer, default=_now)

    remote_account = db.relationship("RemoteAccount", backref="following_records")


# ── Interactions ──────────────────────────────────────────────────


class Favourite(db.Model):
    """Favourited statuses."""

    __tablename__ = "favourites"

    id = db.Column(db.Integer, primary_key=True)
    status_id = db.Column(db.Integer, db.ForeignKey("statuses.id"), nullable=False)
    remote_account_id = db.Column(db.Integer, db.ForeignKey("remote_accounts.id"))
    local = db.Column(db.Boolean, default=True)  # True if our user favourited it
    created_at = db.Column(db.Integer, default=_now)

    status = db.relationship("Status", backref="favourites")
    remote_account = db.relationship("RemoteAccount")


class Bookmark(db.Model):
    """Bookmarked statuses (local only, not federated)."""

    __tablename__ = "bookmarks"

    id = db.Column(db.Integer, primary_key=True)
    status_id = db.Column(db.Integer, db.ForeignKey("statuses.id"), nullable=False)
    created_at = db.Column(db.Integer, default=_now)

    status = db.relationship("Status", backref="bookmarks")


class Mute(db.Model):
    """Muted accounts."""

    __tablename__ = "mutes"

    id = db.Column(db.Integer, primary_key=True)
    remote_account_id = db.Column(
        db.Integer, db.ForeignKey("remote_accounts.id"), nullable=False
    )
    notifications = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.Integer, default=_now)

    remote_account = db.relationship("RemoteAccount")


class Block(db.Model):
    """Blocked accounts."""

    __tablename__ = "blocks"

    id = db.Column(db.Integer, primary_key=True)
    remote_account_id = db.Column(
        db.Integer, db.ForeignKey("remote_accounts.id"), nullable=False
    )
    created_at = db.Column(db.Integer, default=_now)

    remote_account = db.relationship("RemoteAccount")


# ── Notifications ─────────────────────────────────────────────────


class Notification(db.Model):
    """Notifications for the local user."""

    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(
        db.String(32), nullable=False
    )  # mention|status|reblog|follow|follow_request|favourite|poll|update
    remote_account_id = db.Column(db.Integer, db.ForeignKey("remote_accounts.id"))
    status_id = db.Column(db.Integer, db.ForeignKey("statuses.id"))
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.Integer, default=_now)

    remote_account = db.relationship("RemoteAccount")
    status = db.relationship("Status")


# ── Markers ───────────────────────────────────────────────────────


class Marker(db.Model):
    """Timeline read position markers."""

    __tablename__ = "markers"

    id = db.Column(db.Integer, primary_key=True)
    timeline = db.Column(db.String(32), unique=True, nullable=False)  # home|notifications
    last_read_id = db.Column(db.String(64), nullable=False)
    version = db.Column(db.Integer, default=0)
    updated_at = db.Column(db.Integer, default=_now, onupdate=_now)


# ── Idempotency ──────────────────────────────────────────────────


class IdempotencyKey(db.Model):
    """Prevents duplicate status creation."""

    __tablename__ = "idempotency_keys"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), unique=True, nullable=False, index=True)
    status_id = db.Column(db.Integer, db.ForeignKey("statuses.id"))
    created_at = db.Column(db.Integer, default=_now)

    status = db.relationship("Status")
