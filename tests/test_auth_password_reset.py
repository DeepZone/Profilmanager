import os
import unittest
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///test_auth_password_reset.db"
os.environ["SECRET_KEY"] = "test-secret"

from app import create_app
from app.extensions import db
from app.models import Role, User
from app.services.reset_password_service import ResetPasswordService


class AuthPasswordResetTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(
            TESTING=True,
            WTF_CSRF_ENABLED=False,
            MAIL_ENABLED=True,
            MAIL_SERVER="localhost",
            MAIL_PORT=1025,
            MAIL_USE_TLS=False,
            MAIL_USE_SSL=False,
            MAIL_DEFAULT_SENDER="noreply@test.local",
            APP_BASE_URL="http://localhost:5000",
            RESET_PASSWORD_TOKEN_MAX_AGE=3600,
        )
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()

        role = Role(name="User", description="User")
        db.session.add(role)
        db.session.flush()

        self.user = User(
            username="reset-user",
            email="reset@example.com",
            shortcode="RST",
            role_id=role.id,
            active=True,
        )
        self.user.set_password("OldPassword123!")
        db.session.add(self.user)
        db.session.commit()

        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_forgot_password_page_is_available(self):
        response = self.client.get("/forgot-password")
        self.assertEqual(200, response.status_code)

    @patch("app.routes.auth.EmailService.send_mail")
    def test_forgot_password_sends_email_for_known_user(self, mock_send):
        response = self.client.post(
            "/forgot-password",
            data={"email": "reset@example.com"},
            follow_redirects=True,
        )

        self.assertEqual(200, response.status_code)
        mock_send.assert_called_once()

    def test_reset_password_with_valid_token_changes_password(self):
        token = ResetPasswordService.create_token(self.app.config["SECRET_KEY"], self.user.id)

        response = self.client.post(
            f"/reset-password/{token}",
            data={
                "password": "NewPassword123!",
                "confirm_password": "NewPassword123!",
            },
            follow_redirects=True,
        )

        self.assertEqual(200, response.status_code)

        updated_user = User.query.filter_by(id=self.user.id).first()
        self.assertTrue(updated_user.check_password("NewPassword123!"))

    def test_reset_password_with_invalid_token_redirects(self):
        response = self.client.get("/reset-password/invalid-token", follow_redirects=True)

        self.assertEqual(200, response.status_code)
        self.assertIn("Der Link ist ungültig oder abgelaufen.", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
