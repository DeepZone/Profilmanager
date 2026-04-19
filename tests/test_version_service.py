import os
import unittest

os.environ["DATABASE_URL"] = "sqlite:///test_version.db"
os.environ["SECRET_KEY"] = "test-secret"

from app import create_app
from app.extensions import db
from app.models import GitLabMergeRequest, Profile, Role, User
from app.services.version_service import VersionService


class VersionServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(
            TESTING=True,
            WTF_CSRF_ENABLED=False,
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
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
            role=admin_role,
            active=True,
            password_hash="hash",
        )
        self.owner = User(
            username="owner",
            email="owner@example.com",
            role=user_role,
            active=True,
            password_hash="hash",
        )
        db.session.add_all([self.admin, self.owner])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_initialize_defaults_to_1_0_0(self):
        version = VersionService.initialize_version_if_missing()
        self.assertEqual(version.as_string(), "1.0.0")

    def test_increment_build(self):
        VersionService.initialize_version_if_missing()
        new_version = VersionService.increment_build(user_id=self.admin.id, reason="test")
        self.assertEqual(new_version.as_string(), "1.0.1")

    def test_set_minor_resets_build(self):
        VersionService.initialize_version_if_missing()
        VersionService.increment_build(user_id=self.admin.id, reason="test")

        new_version = VersionService.set_minor(3, user_id=self.admin.id)
        self.assertEqual(new_version.as_string(), "1.3.0")

    def test_set_major_resets_minor_and_build(self):
        VersionService.initialize_version_if_missing()
        VersionService.set_minor(4, user_id=self.admin.id)
        VersionService.increment_build(user_id=self.admin.id, reason="test")

        new_version = VersionService.set_major(2, user_id=self.admin.id)
        self.assertEqual(new_version.as_string(), "2.0.0")

    def test_failed_merge_does_not_increment_build(self):
        VersionService.initialize_version_if_missing()

        version_before = VersionService.get_version_string()

        version_after = VersionService.get_version_string()
        self.assertEqual(version_before, version_after)

    def test_successful_merge_increments_build(self):
        VersionService.initialize_version_if_missing()

        profile = Profile(name="Test", user_id=self.owner.id)
        db.session.add(profile)
        db.session.flush()

        mr = GitLabMergeRequest(
            profile_id=profile.id,
            created_by=self.owner.id,
            project_id=123,
            branch_name="feature/x",
            target_branch="main",
            gitlab_mr_iid=42,
            gitlab_mr_id=4242,
            title="MR",
            status="opened",
        )
        db.session.add(mr)
        db.session.commit()

        VersionService.increment_build(user_id=self.admin.id, reason=f"merge_request_{mr.gitlab_mr_iid}")
        self.assertEqual(VersionService.get_version_string(), "1.0.1")


if __name__ == "__main__":
    unittest.main()
