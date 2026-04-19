import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///test_profile_file_cleanup.db"
os.environ["SECRET_KEY"] = "test-secret"

from app import create_app
from app.extensions import db
from app.models import Profile, ProfileFile, Role, User


class ProfileFileCleanupTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app()
        self.app.config.update(
            TESTING=True,
            WTF_CSRF_ENABLED=False,
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            UPLOAD_FOLDER=self.temp_dir.name,
        )
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()

        admin_role = Role(name="Admin", description="Administrator")
        user_role = Role(name="User", description="Standardbenutzer")
        db.session.add_all([admin_role, user_role])
        db.session.flush()

        self.admin = User(
            username="admin",
            email="admin@example.com",
            shortcode="ADM",
            role=admin_role,
            active=True,
            password_hash="hash",
        )
        self.user = User(
            username="owner",
            email="owner@example.com",
            shortcode="OWN",
            role=user_role,
            active=True,
            password_hash="hash",
        )
        self.profile = Profile(name="Testprofil", owner=self.user)
        db.session.add_all([self.admin, self.user, self.profile])
        db.session.flush()

        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()
        self.temp_dir.cleanup()

    def _login(self, user_id: int):
        with self.client.session_transaction() as sess:
            sess["_user_id"] = str(user_id)
            sess["_fresh"] = True

    def _create_profile_file(self, *, profile_id, filename: str) -> ProfileFile:
        path = Path(self.temp_dir.name) / filename
        path.write_bytes(b"dummy")

        pf = ProfileFile(
            profile_id=profile_id,
            version=1,
            original_filename=filename,
            stored_path=str(path),
            mime_type="application/octet-stream",
            file_size=5,
            sha256="abc",
        )
        db.session.add(pf)
        db.session.commit()
        return pf

    def test_profile_delete_removes_local_file_even_when_keep_dependencies_selected(self):
        profile_file = self._create_profile_file(profile_id=self.profile.id, filename="owned.tar")
        stored_path = profile_file.stored_path
        self._login(self.user.id)

        with patch("app.routes.profiles._delete_profile_files_from_git", return_value=None):
            response = self.client.post(
                f"/profiles/{self.profile.id}/delete",
                data={"keep_dependencies": "1"},
                follow_redirects=False,
        )

        self.assertEqual(302, response.status_code)
        self.assertFalse(Path(stored_path).exists())
        self.assertIsNone(Profile.query.get(self.profile.id))
        self.assertEqual(0, ProfileFile.query.count())

    def test_admin_can_delete_orphan_file(self):
        orphan_file = self._create_profile_file(profile_id=None, filename="orphan.tar")
        self._login(self.admin.id)

        response = self.client.post(
            f"/profiles/orphan-files/{orphan_file.id}/delete",
            follow_redirects=False,
        )

        self.assertEqual(302, response.status_code)
        self.assertFalse(Path(orphan_file.stored_path).exists())
        self.assertIsNone(ProfileFile.query.get(orphan_file.id))


if __name__ == "__main__":
    unittest.main()
