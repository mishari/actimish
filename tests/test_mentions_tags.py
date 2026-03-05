import tempfile
import unittest

from tests.helpers import fresh_app, make_token, close_db


class TestMentionsAndTags(unittest.TestCase):
    def test_create_status_populates_mentions_and_tags(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            flask_app, models = fresh_app(tmpdir)
            make_token(flask_app, models)

            client = flask_app.test_client()
            resp = client.post(
                "/api/v1/statuses",
                json={"status": "Hello @alice@example.com #TestTag"},
                headers={"Authorization": "Bearer testtoken"},
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()

            self.assertIsInstance(data.get("mentions"), list)
            self.assertIsInstance(data.get("tags"), list)

            self.assertEqual(len(data["mentions"]), 1)
            self.assertEqual(data["mentions"][0].get("acct"), "alice@example.com")
            self.assertEqual(data["mentions"][0].get("username"), "alice")

            self.assertEqual(len(data["tags"]), 1)
            self.assertEqual(data["tags"][0].get("name"), "testtag")

            close_db(flask_app, models)
