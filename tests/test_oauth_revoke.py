import tempfile
import unittest

from tests.helpers import fresh_app, make_token, close_db


class TestOAuthRevoke(unittest.TestCase):
    def test_revoke_returns_json_and_marks_token_revoked(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            flask_app, models = fresh_app(tmpdir)
            make_token(flask_app, models, access_token="torevoke")
            client = flask_app.test_client()

            resp = client.post("/oauth/revoke", data={"token": "torevoke"})
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.get_json(), {})

            with flask_app.app_context():
                tok = models.OAuthToken.query.filter_by(access_token="torevoke").first()
                self.assertIsNotNone(tok)
                self.assertTrue(tok.revoked)

            close_db(flask_app, models)
