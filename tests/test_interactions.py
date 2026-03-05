import tempfile
import unittest

from tests.helpers import fresh_app, make_token, close_db


class TestInteractions(unittest.TestCase):
    def test_favourite_and_unfavourite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            flask_app, models = fresh_app(tmpdir)
            make_token(flask_app, models)
            client = flask_app.test_client()

            created = client.post(
                "/api/v1/statuses",
                json={"status": "hi"},
                headers={"Authorization": "Bearer testtoken"},
            ).get_json()
            sid = created["id"]

            fav = client.post(
                f"/api/v1/statuses/{sid}/favourite",
                headers={"Authorization": "Bearer testtoken"},
            )
            self.assertEqual(fav.status_code, 200)
            data = fav.get_json()
            self.assertTrue(data.get("favourited"))
            self.assertGreaterEqual(data.get("favourites_count", 0), 1)

            unfav = client.post(
                f"/api/v1/statuses/{sid}/unfavourite",
                headers={"Authorization": "Bearer testtoken"},
            )
            self.assertEqual(unfav.status_code, 200)
            data = unfav.get_json()
            self.assertFalse(data.get("favourited"))

            close_db(flask_app, models)

    def test_bookmark_and_unbookmark(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            flask_app, models = fresh_app(tmpdir)
            make_token(flask_app, models)
            client = flask_app.test_client()

            created = client.post(
                "/api/v1/statuses",
                json={"status": "hi"},
                headers={"Authorization": "Bearer testtoken"},
            ).get_json()
            sid = created["id"]

            bm = client.post(
                f"/api/v1/statuses/{sid}/bookmark",
                headers={"Authorization": "Bearer testtoken"},
            )
            self.assertEqual(bm.status_code, 200)
            self.assertTrue(bm.get_json().get("bookmarked"))

            unbm = client.post(
                f"/api/v1/statuses/{sid}/unbookmark",
                headers={"Authorization": "Bearer testtoken"},
            )
            self.assertEqual(unbm.status_code, 200)
            self.assertFalse(unbm.get_json().get("bookmarked"))

            close_db(flask_app, models)
