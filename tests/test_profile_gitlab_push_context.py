import os
import unittest
from datetime import datetime, timedelta

os.environ["DATABASE_URL"] = "sqlite:///test_profile_gitlab_push_context.db"
os.environ["SECRET_KEY"] = "test-secret"

from app import create_app
from app.extensions import db
from app.models import GitLabMergeRequest, Profile, Role, User
from app.routes.profiles import _get_profile_gitlab_push_context


class ProfileGitLabPushContextTestCase(unittest.TestCase):
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

        role = Role(name="User", description="Standardbenutzer")
        user = User(
            username="owner",
            email="owner@example.com",
            shortcode="OWN",
            role=role,
            active=True,
            password_hash="hash",
        )
        profile = Profile(name="Testprofil", owner=user)
        db.session.add_all([role, user, profile])
        db.session.commit()
        self.profile = profile
        self.user = user

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _add_mr(self, status: str, *, iid: int, title: str, created_at: datetime, web_url: str = ""):
        mr = GitLabMergeRequest(
            profile_id=self.profile.id,
            created_by=self.user.id,
            project_id=123,
            branch_name=f"feature/{iid}",
            target_branch="main",
            gitlab_mr_iid=iid,
            gitlab_mr_id=1000 + iid,
            title=title,
            status=status,
            web_url=web_url or None,
            created_at=created_at,
            updated_at=created_at,
        )
        db.session.add(mr)
        db.session.commit()
        return mr

    def test_shows_push_form_when_no_open_mr_exists(self):
        context = _get_profile_gitlab_push_context(self.profile.id)
        self.assertTrue(context["show_push_form"])
        self.assertIsNone(context["open_mr"])

    def test_hides_push_form_when_open_mr_exists(self):
        now = datetime.utcnow()
        self._add_mr(status="opened", iid=11, title="Offen", created_at=now)

        context = _get_profile_gitlab_push_context(self.profile.id)
        self.assertFalse(context["show_push_form"])
        self.assertEqual(11, context["open_mr"].gitlab_mr_iid)

    def test_provides_latest_merged_mr_when_available(self):
        now = datetime.utcnow()
        self._add_mr(
            status="merged",
            iid=20,
            title="Altes Merge",
            created_at=now - timedelta(days=1),
            web_url="https://gitlab.example.com/old",
        )
        self._add_mr(
            status="merged",
            iid=21,
            title="Neues Merge",
            created_at=now,
            web_url="https://gitlab.example.com/new",
        )

        context = _get_profile_gitlab_push_context(self.profile.id)
        self.assertTrue(context["show_push_form"])
        self.assertEqual(21, context["latest_merged_mr"].gitlab_mr_iid)
        self.assertEqual("https://gitlab.example.com/new", context["latest_merged_mr"].web_url)


if __name__ == "__main__":
    unittest.main()
