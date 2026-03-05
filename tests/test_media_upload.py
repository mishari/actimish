import io
import os
import tempfile
import unittest

from tests.helpers import fresh_app, make_token, close_db


class TestMediaUpload(unittest.TestCase):
    def test_upload_png_image(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            flask_app, models = fresh_app(tmpdir)
            make_token(flask_app, models)

            from PIL import Image

            bio = io.BytesIO()
            Image.new("RGB", (32, 32), color=(10, 20, 30)).save(bio, format="PNG")
            png_bytes = bio.getvalue()
            client = flask_app.test_client()
            resp = client.post(
                "/api/v2/media",
                data={"file": (io.BytesIO(png_bytes), "test.png")},
                content_type="multipart/form-data",
                headers={"Authorization": "Bearer testtoken"},
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertEqual(data.get("type"), "image")
            self.assertIn("/media/", data.get("url", ""))
            self.assertIn("/media/", data.get("preview_url", ""))
            self.assertNotEqual(data.get("preview_url"), data.get("url"))

            rel = data["url"].split("/media/", 1)[1]
            full_path = os.path.join(tmpdir, "media", rel)
            self.assertTrue(os.path.isfile(full_path))

            preview_rel = data["preview_url"].split("/media/", 1)[1]
            preview_path = os.path.join(tmpdir, "media", preview_rel)
            self.assertTrue(os.path.isfile(preview_path))

            close_db(flask_app, models)

    def test_upload_mp4_video(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            flask_app, models = fresh_app(tmpdir)
            make_token(flask_app, models)

            # Minimal bytes to trigger mp4 detection (header_bytes[4:8] == b"ftyp").
            mp4_bytes = b"\x00\x00\x00\x18ftyp" + (b"0" * 256)
            client = flask_app.test_client()
            resp = client.post(
                "/api/v2/media",
                data={"file": (io.BytesIO(mp4_bytes), "clip.mp4")},
                content_type="multipart/form-data",
                headers={"Authorization": "Bearer testtoken"},
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertEqual(data.get("type"), "video")
            self.assertIn("/media/", data.get("url", ""))

            # Videos may not have a generated preview; allow preview_url==url.
            self.assertIn("/media/", data.get("preview_url", ""))

            rel = data["url"].split("/media/", 1)[1]
            full_path = os.path.join(tmpdir, "media", rel)
            self.assertTrue(os.path.isfile(full_path))

            close_db(flask_app, models)
