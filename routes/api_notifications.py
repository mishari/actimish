"""
Mastodon API: Notification endpoints.
"""

from flask import Blueprint, request, jsonify
import config
from models import db, Notification
from utils.auth import require_auth
from utils.serializers import serialize_notification

api_notifications_bp = Blueprint("api_notifications", __name__)


@api_notifications_bp.route("/api/v1/notifications", methods=["GET"])
@require_auth
def list_notifications():
    limit = min(int(request.args.get("limit", 15)), 30)
    max_id = request.args.get("max_id")
    min_id = request.args.get("min_id")
    since_id = request.args.get("since_id")
    types = request.args.getlist("types[]")
    exclude_types = request.args.getlist("exclude_types[]")

    query = Notification.query

    if max_id:
        query = query.filter(Notification.id < int(max_id))
    if min_id:
        query = query.filter(Notification.id > int(min_id))
    if since_id:
        query = query.filter(Notification.id > int(since_id))
    if types:
        query = query.filter(Notification.type.in_(types))
    if exclude_types:
        query = query.filter(Notification.type.notin_(exclude_types))

    notifications = query.order_by(Notification.id.desc()).limit(limit).all()

    result = [serialize_notification(n) for n in notifications]

    response = jsonify(result)
    if notifications:
        base = f"https://{config.DOMAIN}"
        links = [
            f'<{base}/api/v1/notifications?max_id={notifications[-1].id}>; rel="next"',
            f'<{base}/api/v1/notifications?min_id={notifications[0].id}>; rel="prev"',
        ]
        response.headers["Link"] = ", ".join(links)
    return response


@api_notifications_bp.route("/api/v1/notifications/<int:notif_id>", methods=["GET"])
@require_auth
def get_notification(notif_id):
    notif = Notification.query.get(notif_id)
    if not notif:
        return jsonify({"error": "Record not found"}), 404
    return jsonify(serialize_notification(notif))


@api_notifications_bp.route("/api/v1/notifications/clear", methods=["POST"])
@require_auth
def clear_notifications():
    Notification.query.delete()
    db.session.commit()
    return "{}", 200


@api_notifications_bp.route(
    "/api/v1/notifications/<int:notif_id>/dismiss", methods=["POST"]
)
@require_auth
def dismiss_notification(notif_id):
    notif = Notification.query.get(notif_id)
    if notif:
        db.session.delete(notif)
        db.session.commit()
    return "{}", 200


@api_notifications_bp.route("/api/v1/notifications/unread_count", methods=["GET"])
@require_auth
def unread_count():
    count = Notification.query.filter_by(read=False).count()
    return jsonify({"count": count})
