import tempfile
import unittest

from tests.helpers import fresh_app, make_token, close_db


class TestStatusSource(unittest.TestCase):
    def test_status_source_returns_plain_text(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            flask_app, models = fresh_app(tmpdir)
            make_token(flask_app, models)

            client = flask_app.test_client()
            text = "Line 1\nLine 2\n\nPara 2"
            resp = client.post(
                "/api/v1/statuses",
                json={"status": text},
                headers={"Authorization": "Bearer testtoken"},
            )
            self.assertEqual(resp.status_code, 200)
            status_id = resp.get_json().get("id")
            self.assertIsNotNone(status_id)

            src = client.get(
                f"/api/v1/statuses/{status_id}/source",
                headers={"Authorization": "Bearer testtoken"},
            )
            self.assertEqual(src.status_code, 200)
            data = src.get_json()
            self.assertEqual(data.get("text"), text)

            close_db(flask_app, models)

    def test_delete_status_includes_plain_text_for_redraft(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            flask_app, models = fresh_app(tmpdir)
            make_token(flask_app, models)

            client = flask_app.test_client()
            text = "Hello\nworld"
            resp = client.post(
                "/api/v1/statuses",
                json={"status": text},
                headers={"Authorization": "Bearer testtoken"},
            )
            status_id = resp.get_json().get("id")

            deleted = client.delete(
                f"/api/v1/statuses/{status_id}",
                headers={"Authorization": "Bearer testtoken"},
            )
            self.assertEqual(deleted.status_code, 200)
            data = deleted.get_json()
            self.assertEqual(data.get("text"), text)

            close_db(flask_app, models)
