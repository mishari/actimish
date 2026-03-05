import tempfile
import unittest

from tests.helpers import fresh_app, make_token, close_db


class TestSearchVisibility(unittest.TestCase):
    def test_search_does_not_leak_private_statuses_without_auth(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            flask_app, models = fresh_app(tmpdir)
            make_token(flask_app, models)
            client = flask_app.test_client()

            created = client.post(
                "/api/v1/statuses",
                json={"status": "verysecret", "visibility": "private"},
                headers={"Authorization": "Bearer testtoken"},
            )
            self.assertEqual(created.status_code, 200)

            unauth = client.get("/api/v2/search?q=verysecret&type=statuses")
            self.assertEqual(unauth.status_code, 200)
            data = unauth.get_json()
            self.assertEqual(data.get("statuses"), [])

            authed = client.get(
                "/api/v2/search?q=verysecret&type=statuses",
                headers={"Authorization": "Bearer testtoken"},
            )
            self.assertEqual(authed.status_code, 200)
            data = authed.get_json()
            self.assertEqual(len(data.get("statuses", [])), 1)

            close_db(flask_app, models)
