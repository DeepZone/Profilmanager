import os
import unittest

os.environ["DATABASE_URL"] = "sqlite:///test_settings_routes.db"
os.environ["SECRET_KEY"] = "test-secret"

from app import create_app
from app.extensions import db
from app.models import Role, Setting, User


class SettingsRoutesTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()

        admin_role = Role(name="Admin", description="Admin")
        user_role = Role(name="User", description="User")
        db.session.add_all([admin_role, user_role])
        db.session.flush()

        self.admin = User(
            username="admin",
            email="admin@example.com",
            shortcode="ADM",
            role_id=admin_role.id,
            active=True,
        )
        self.admin.set_password("AdminPass123!")

        self.user = User(
            username="user",
            email="user@example.com",
            shortcode="USR",
            role_id=user_role.id,
            active=True,
        )
        self.user.set_password("UserPass123!")

        db.session.add_all([self.admin, self.user])
        db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _login(self, username, password):
        return self.client.post(
            "/login",
            data={"username": username, "password": password},
            follow_redirects=True,
        )

    def test_settings_route_requires_admin(self):
        self._login("user", "UserPass123!")

        response = self.client.get("/settings")

        self.assertEqual(403, response.status_code)

    def test_admin_can_update_default_sender(self):
        self._login("admin", "AdminPass123!")

        response = self.client.post(
            "/settings",
            data={"mail_default_sender": "ops@example.com"},
            follow_redirects=True,
        )

        self.assertEqual(200, response.status_code)
        sender_setting = Setting.query.filter_by(key="mail_default_sender").first()
        self.assertIsNotNone(sender_setting)
        self.assertEqual("ops@example.com", sender_setting.value)


if __name__ == "__main__":
    unittest.main()
