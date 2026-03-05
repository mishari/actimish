import tempfile
import unittest

from tests.helpers import fresh_app, make_token, close_db


class TestQueryParamRobustness(unittest.TestCase):
    def test_limit_param_non_int_does_not_500(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            flask_app, models = fresh_app(tmpdir)
            make_token(flask_app, models)
            client = flask_app.test_client()

            resp = client.get(
                "/api/v1/notifications?limit=not-an-int",
                headers={"Authorization": "Bearer testtoken"},
            )
            self.assertEqual(resp.status_code, 200)

            resp = client.get("/api/v2/search?q=hi&limit=not-an-int")
            self.assertEqual(resp.status_code, 200)

            resp = client.get("/api/v1/timelines/public?limit=not-an-int")
            self.assertEqual(resp.status_code, 200)

            resp = client.get("/api/v1/accounts/search?q=a&limit=not-an-int")
            self.assertEqual(resp.status_code, 200)

            close_db(flask_app, models)
