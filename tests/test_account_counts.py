import tempfile
import unittest

from tests.helpers import fresh_app, make_token, close_db


class TestAccountCounts(unittest.TestCase):
    def test_status_account_includes_nonzero_statuses_count(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            flask_app, models = fresh_app(tmpdir)
            make_token(flask_app, models)

            client = flask_app.test_client()
            created = client.post(
                "/api/v1/statuses",
                json={"status": "hello"},
                headers={"Authorization": "Bearer testtoken"},
            )
            self.assertEqual(created.status_code, 200)
            status_id = created.get_json()["id"]

            fetched = client.get(
                f"/api/v1/statuses/{status_id}",
                headers={"Authorization": "Bearer testtoken"},
            )
            self.assertEqual(fetched.status_code, 200)
            data = fetched.get_json()
            acct = data.get("account") or {}
            self.assertGreaterEqual(acct.get("statuses_count", 0), 1)

            close_db(flask_app, models)
