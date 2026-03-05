import tempfile
import unittest

from tests.helpers import fresh_app, make_token, close_db


class TestNotifications(unittest.TestCase):
    def test_list_marks_notifications_read_and_unread_count_updates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            flask_app, models = fresh_app(tmpdir)
            make_token(flask_app, models)

            with flask_app.app_context():
                ra = models.RemoteAccount(
                    uri="https://remote.test/users/alice",
                    url="https://remote.test/@alice",
                    username="alice",
                    domain="remote.test",
                    display_name="Alice",
                    inbox_url="https://remote.test/inbox",
                )
                models.db.session.add(ra)
                models.db.session.flush()

                s = models.Status(
                    uri="https://remote.test/statuses/1",
                    content="<p>Hi</p>",
                    remote=True,
                    remote_account_id=ra.id,
                    remote_url="https://remote.test/@alice/1",
                )
                models.db.session.add(s)
                models.db.session.flush()

                n = models.Notification(
                    type="mention",
                    remote_account_id=ra.id,
                    status_id=s.id,
                    read=False,
                )
                models.db.session.add(n)
                models.db.session.commit()

            client = flask_app.test_client()

            unread_before = client.get(
                "/api/v1/notifications/unread_count",
                headers={"Authorization": "Bearer testtoken"},
            ).get_json()["count"]
            self.assertEqual(unread_before, 1)

            resp = client.get(
                "/api/v1/notifications",
                headers={"Authorization": "Bearer testtoken"},
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0].get("type"), "mention")
            self.assertIn("account", data[0])
            self.assertIn("created_at", data[0])
            self.assertIn("status", data[0])

            unread_after = client.get(
                "/api/v1/notifications/unread_count",
                headers={"Authorization": "Bearer testtoken"},
            ).get_json()["count"]
            self.assertEqual(unread_after, 0)

            close_db(flask_app, models)

    def test_dismiss_and_clear_return_json_object(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            flask_app, models = fresh_app(tmpdir)
            make_token(flask_app, models)

            with flask_app.app_context():
                n = models.Notification(type="follow", read=False)
                models.db.session.add(n)
                models.db.session.commit()
                notif_id = n.id

            client = flask_app.test_client()

            dismiss = client.post(
                f"/api/v1/notifications/{notif_id}/dismiss",
                headers={"Authorization": "Bearer testtoken"},
            )
            self.assertEqual(dismiss.status_code, 200)
            self.assertEqual(dismiss.get_json(), {})

            clear = client.post(
                "/api/v1/notifications/clear",
                headers={"Authorization": "Bearer testtoken"},
            )
            self.assertEqual(clear.status_code, 200)
            self.assertEqual(clear.get_json(), {})

            close_db(flask_app, models)
