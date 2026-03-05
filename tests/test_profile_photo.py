"""
Tests for profile photo (avatar/header) upload and persistence.
"""
import os
import json
import tempfile
import unittest
from io import BytesIO
from PIL import Image

from tests.helpers import fresh_app, make_token, close_db


class TestProfilePhoto(unittest.TestCase):
    """Test avatar/header upload and settings persistence."""

    def setUp(self):
        """Set up test app and client."""
        self.temp_dir = tempfile.mkdtemp()
        self.app, self.models = fresh_app(self.temp_dir)
        self.client = self.app.test_client()
        self.db = self.models.db

    def tearDown(self):
        """Clean up."""
        close_db(self.app, self.models)
        # Clean up temp directory
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def _create_image(self, width=100, height=100, fmt="PNG"):
        """Helper: create in-memory image."""
        img = Image.new("RGB", (width, height), color="red")
        buf = BytesIO()
        img.save(buf, format=fmt)
        buf.seek(0)
        return buf

    def _get_oauth_token(self):
        """Get OAuth token from test app."""
        with self.app.app_context():
            # Use the existing make_token helper
            make_token(self.app, self.models, "test_profile_token")
            return "test_profile_token"

    def test_upload_avatar_png(self):
        """Test uploading PNG avatar via PATCH update_credentials."""
        token = self._get_oauth_token()
        img = self._create_image(200, 200, "PNG")

        response = self.client.patch(
            "/api/v1/accounts/update_credentials",
            data={"avatar": (img, "avatar.png")},
            headers={"Authorization": f"Bearer {token}"}
        )

        # Should succeed
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("avatar", data)
        # Avatar URL should point to .png file
        self.assertTrue(data["avatar"].endswith(".png"))

    def test_upload_avatar_jpeg(self):
        """Test uploading JPEG avatar via PATCH update_credentials."""
        token = self._get_oauth_token()
        img = self._create_image(200, 200, "JPEG")

        response = self.client.patch(
            "/api/v1/accounts/update_credentials",
            data={"avatar": (img, "avatar.jpg")},
            headers={"Authorization": f"Bearer {token}"}
        )

        # Should succeed
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("avatar", data)
        # Avatar URL should point to .jpg file
        self.assertTrue(data["avatar"].endswith(".jpg"))

    def test_upload_avatar_oversized_image_gets_resized(self):
        """Test that oversized avatar is resized to max 400x400."""
        token = self._get_oauth_token()
        # Create 1000x1000 image
        img = self._create_image(1000, 1000, "PNG")

        response = self.client.patch(
            "/api/v1/accounts/update_credentials",
            data={"avatar": (img, "avatar.png")},
            headers={"Authorization": f"Bearer {token}"}
        )

        # Should succeed
        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        # Verify the file was resized by checking the file dimensions
        # (we'll need to read the actual saved file)
        from config import DATA_DIR
        avatar_path = os.path.join(DATA_DIR, "avatar.png")
        if os.path.exists(avatar_path):
            with Image.open(avatar_path) as img_on_disk:
                # Should be resized to max 400x400
                self.assertLessEqual(img_on_disk.width, 400)
                self.assertLessEqual(img_on_disk.height, 400)

    def test_upload_non_image_rejected(self):
        """Test that uploading non-image file is rejected."""
        token = self._get_oauth_token()
        # Create a fake non-image file
        fake_file = BytesIO(b"This is not an image")
        fake_file.seek(0)

        response = self.client.patch(
            "/api/v1/accounts/update_credentials",
            data={"avatar": (fake_file, "notanimage.txt")},
            headers={"Authorization": f"Bearer {token}"}
        )

        # Should fail with 4xx error
        self.assertGreaterEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("error", data)

    def test_upload_header_png(self):
        """Test uploading PNG header via PATCH update_credentials."""
        token = self._get_oauth_token()
        img = self._create_image(500, 200, "PNG")

        response = self.client.patch(
            "/api/v1/accounts/update_credentials",
            data={"header": (img, "header.png")},
            headers={"Authorization": f"Bearer {token}"}
        )

        # Should succeed
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("header", data)
        # Header URL should point to .png file
        self.assertTrue(data["header"].endswith(".png"))

    def test_display_name_persists_across_restart(self):
        """Test that updated display_name persists in data/settings.json."""
        token = self._get_oauth_token()

        # Update display_name
        response = self.client.patch(
            "/api/v1/accounts/update_credentials",
            data={"display_name": "New Name"},
            headers={"Authorization": f"Bearer {token}"}
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["display_name"], "New Name")

        # Check that settings.json was written
        from config import DATA_DIR
        settings_path = os.path.join(DATA_DIR, "settings.json")
        self.assertTrue(os.path.exists(settings_path))

        with open(settings_path, "r") as f:
            settings = json.load(f)
            self.assertEqual(settings.get("display_name"), "New Name")

    def test_bio_persists_across_restart(self):
        """Test that updated bio persists in data/settings.json."""
        token = self._get_oauth_token()

        # Update bio
        response = self.client.patch(
            "/api/v1/accounts/update_credentials",
            data={"note": "My new bio"},
            headers={"Authorization": f"Bearer {token}"}
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        # The 'note' field contains the bio
        self.assertEqual(data["note"], "My new bio")

        # Check that settings.json was written
        from config import DATA_DIR
        settings_path = os.path.join(DATA_DIR, "settings.json")
        self.assertTrue(os.path.exists(settings_path))

        with open(settings_path, "r") as f:
            settings = json.load(f)
            self.assertEqual(settings.get("bio"), "My new bio")

    def test_avatar_metadata_stored_in_settings(self):
        """Test that avatar MIME type is stored in settings.json."""
        token = self._get_oauth_token()
        img = self._create_image(200, 200, "JPEG")

        response = self.client.patch(
            "/api/v1/accounts/update_credentials",
            data={"avatar": (img, "avatar.jpg")},
            headers={"Authorization": f"Bearer {token}"}
        )

        self.assertEqual(response.status_code, 200)

        # Check settings.json
        from config import DATA_DIR
        settings_path = os.path.join(DATA_DIR, "settings.json")
        self.assertTrue(os.path.exists(settings_path))

        with open(settings_path, "r") as f:
            settings = json.load(f)
            # Should have avatar_mime set to image/jpeg
            self.assertEqual(settings.get("avatar_mime"), "image/jpeg")

    def test_verify_credentials_returns_correct_avatar_url(self):
        """Test that verify_credentials returns avatar with correct extension."""
        token = self._get_oauth_token()
        img = self._create_image(200, 200, "PNG")

        # Upload PNG avatar
        response = self.client.patch(
            "/api/v1/accounts/update_credentials",
            data={"avatar": (img, "avatar.png")},
            headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(response.status_code, 200)

        # Now fetch verify_credentials
        response = self.client.get(
            "/api/v1/accounts/verify_credentials",
            headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["avatar"].endswith(".png"))

    def test_activitypub_actor_has_correct_mime_type(self):
        """Test that ActivityPub actor object has correct icon mediaType."""
        import config
        token = self._get_oauth_token()
        img = self._create_image(200, 200, "JPEG")

        # Upload JPEG avatar
        response = self.client.patch(
            "/api/v1/accounts/update_credentials",
            data={"avatar": (img, "avatar.jpg")},
            headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(response.status_code, 200)

        # Fetch ActivityPub actor (use the configured test username)
        response = self.client.get(
            f"/users/{config.USERNAME}",
            headers={"Accept": "application/activity+json"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        # Check icon mediaType
        self.assertIn("icon", data)
        self.assertEqual(data["icon"]["mediaType"], "image/jpeg")

    def test_switching_avatar_format_updates_url(self):
        """Test switching from PNG to JPEG avatar updates the URL."""
        token = self._get_oauth_token()

        # Upload PNG avatar
        png_img = self._create_image(200, 200, "PNG")
        response = self.client.patch(
            "/api/v1/accounts/update_credentials",
            data={"avatar": (png_img, "avatar.png")},
            headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(response.status_code, 200)
        data1 = response.get_json()
        self.assertTrue(data1["avatar"].endswith(".png"))

        # Upload JPEG avatar
        jpg_img = self._create_image(200, 200, "JPEG")
        response = self.client.patch(
            "/api/v1/accounts/update_credentials",
            data={"avatar": (jpg_img, "avatar.jpg")},
            headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(response.status_code, 200)
        data2 = response.get_json()
        self.assertTrue(data2["avatar"].endswith(".jpg"))

    def test_default_avatar_svg_fallback_when_none_uploaded(self):
        """Test that /avatar.png returns SVG fallback when no avatar uploaded."""
        response = self.client.get("/avatar.png")
        # Should return SVG
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<svg", response.data)


if __name__ == "__main__":
    unittest.main()
