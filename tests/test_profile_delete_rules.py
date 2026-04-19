import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///test_profile_delete_rules.db"
os.environ["SECRET_KEY"] = "test-secret"

from app import create_app
from app.extensions import db
from app.models import GitLabMergeRequest, Profile, Role, User
from app.routes.profiles import _get_profile_delete_block_reason


class ProfileDeleteRulesTestCase(unittest.TestCase):
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
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _add_mr(self, status: str):
        db.session.add(
            GitLabMergeRequest(
                profile_id=self.profile.id,
                created_by=self.user.id,
                project_id=123,
                branch_name=f"feature/{status}",
                target_branch="main",
                gitlab_mr_iid=100 + GitLabMergeRequest.query.count(),
                gitlab_mr_id=200 + GitLabMergeRequest.query.count(),
                title=f"MR {status}",
                status=status,
            )
        )
        db.session.commit()

    def test_allows_delete_without_mrs(self):
        with patch("app.routes.profiles.current_user", SimpleNamespace(is_admin=False)):
            self.assertIsNone(_get_profile_delete_block_reason(self.profile))

    def test_blocks_when_more_than_one_open_mr(self):
        self._add_mr("opened")
        self._add_mr("opened")

        with patch("app.routes.profiles.current_user", SimpleNamespace(is_admin=True)):
            reason = _get_profile_delete_block_reason(self.profile)

        self.assertIn("kein oder nur ein offener Merge Request", reason)

    def test_blocks_non_admin_when_profile_has_merged_mr(self):
        self._add_mr("merged")

        with patch("app.routes.profiles.current_user", SimpleNamespace(is_admin=False)):
            reason = _get_profile_delete_block_reason(self.profile)

        self.assertEqual("Gemergte Profile dürfen nur von einem Admin gelöscht werden.", reason)

    def test_allows_admin_when_profile_has_merged_mr(self):
        self._add_mr("merged")

        with patch("app.routes.profiles.current_user", SimpleNamespace(is_admin=True)):
            self.assertIsNone(_get_profile_delete_block_reason(self.profile))


if __name__ == "__main__":
    unittest.main()
