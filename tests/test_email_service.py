import smtplib
import unittest
from unittest.mock import MagicMock, patch

from app.services.email_service import EmailService


class EmailServiceTestCase(unittest.TestCase):
    @patch("app.services.email_service.smtplib.SMTP")
    def test_send_mail_falls_back_when_starttls_is_not_supported(self, mock_smtp):
        smtp_instance = MagicMock()
        smtp_instance.starttls.side_effect = smtplib.SMTPNotSupportedError("STARTTLS not supported")
        mock_smtp.return_value.__enter__.return_value = smtp_instance

        EmailService.send_mail(
            smtp_host="localhost",
            smtp_port=1025,
            sender="noreply@test.local",
            recipient="user@test.local",
            subject="Reset",
            body="Body",
            use_tls=True,
            use_ssl=False,
        )

        smtp_instance.starttls.assert_called_once()
        smtp_instance.send_message.assert_called_once()


if __name__ == "__main__":
    unittest.main()
