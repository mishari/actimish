import tempfile
import unittest

from tests.helpers import fresh_app, make_token, close_db


class TestVisibility(unittest.TestCase):
    def test_private_status_not_visible_without_auth(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            flask_app, models = fresh_app(tmpdir)
            make_token(flask_app, models)
            client = flask_app.test_client()

            created = client.post(
                "/api/v1/statuses",
                json={"status": "secret", "visibility": "private"},
                headers={"Authorization": "Bearer testtoken"},
            )
            self.assertEqual(created.status_code, 200)
            status_id = created.get_json()["id"]

            unauth = client.get(f"/api/v1/statuses/{status_id}")
            self.assertEqual(unauth.status_code, 404)
            self.assertEqual(unauth.get_json().get("error"), "Record not found")

            authed = client.get(
                f"/api/v1/statuses/{status_id}",
                headers={"Authorization": "Bearer testtoken"},
            )
            self.assertEqual(authed.status_code, 200)

            close_db(flask_app, models)
