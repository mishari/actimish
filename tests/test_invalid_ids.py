import tempfile
import unittest

from tests.helpers import fresh_app, make_token, close_db


class TestInvalidIds(unittest.TestCase):
    def test_get_status_with_invalid_id_returns_json_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            flask_app, models = fresh_app(tmpdir)
            client = flask_app.test_client()

            resp = client.get("/api/v1/statuses/not-an-int")
            self.assertEqual(resp.status_code, 404)
            data = resp.get_json()
            self.assertEqual(data.get("error"), "Record not found")

            close_db(flask_app, models)

    def test_delete_status_with_invalid_id_returns_json_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            flask_app, models = fresh_app(tmpdir)
            make_token(flask_app, models)
            client = flask_app.test_client()

            resp = client.delete(
                "/api/v1/statuses/not-an-int",
                headers={"Authorization": "Bearer testtoken"},
            )
            self.assertEqual(resp.status_code, 404)
            data = resp.get_json()
            self.assertEqual(data.get("error"), "Record not found")

            close_db(flask_app, models)

    def test_get_remote_account_with_invalid_id_returns_json_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            flask_app, models = fresh_app(tmpdir)
            client = flask_app.test_client()

            resp = client.get("/api/v1/accounts/not-an-int")
            self.assertEqual(resp.status_code, 404)
            data = resp.get_json()
            self.assertEqual(data.get("error"), "Record not found")

            close_db(flask_app, models)
