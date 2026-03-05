import tempfile
import unittest

from tests.helpers import fresh_app, make_token, close_db

class TestStatusLimits(unittest.TestCase):
    def test_create_status_allows_very_long_text(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            flask_app, models = fresh_app(tmpdir)
            make_token(flask_app, models)

            # 1MB-ish plain text; should not be rejected or truncated.
            long_text = "a" * (1024 * 1024)

            client = flask_app.test_client()
            resp = client.post(
                "/api/v1/statuses",
                json={"status": long_text, "visibility": "public"},
                headers={"Authorization": "Bearer testtoken"},
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertIsInstance(data, dict)
            self.assertIn("content", data)
            self.assertTrue(data["content"].startswith("<p>"))

            with flask_app.app_context():
                s = models.Status.query.order_by(models.Status.id.desc()).first()
                self.assertIsNotNone(s)
                self.assertGreater(len(s.content), len(long_text))
                self.assertIn(long_text[:64], s.content)

            close_db(flask_app, models)

    def test_instance_reports_effectively_unlimited_characters(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            flask_app, models = fresh_app(tmpdir)

            client = flask_app.test_client()
            resp = client.get("/api/v1/instance")
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            max_chars = data["configuration"]["statuses"]["max_characters"]
            self.assertGreaterEqual(max_chars, 2_000_000_000)

            close_db(flask_app, models)
