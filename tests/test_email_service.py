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

    @patch("app.services.email_service.smtplib.SMTP")
    def test_send_mail_retries_with_mailhog_when_localhost_is_unreachable(self, mock_smtp):
        smtp_instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = smtp_instance
        mock_smtp.side_effect = [ConnectionRefusedError("refused"), mock_smtp.return_value]

        EmailService.send_mail(
            smtp_host="localhost",
            smtp_port=1025,
            sender="noreply@test.local",
            recipient="user@test.local",
            subject="Reset",
            body="Body",
            use_tls=False,
            use_ssl=False,
        )

        self.assertEqual(2, mock_smtp.call_count)
        self.assertEqual(("localhost", 1025), mock_smtp.call_args_list[0].args)
        self.assertEqual(("mailhog", 1025), mock_smtp.call_args_list[1].args)
        smtp_instance.send_message.assert_called_once()

    @patch("app.services.email_service.smtplib.SMTP")
    def test_send_mail_does_not_retry_other_hosts_on_connection_refused(self, mock_smtp):
        mock_smtp.side_effect = ConnectionRefusedError("refused")

        with self.assertRaises(ConnectionRefusedError):
            EmailService.send_mail(
                smtp_host="smtp.example.com",
                smtp_port=25,
                sender="noreply@test.local",
                recipient="user@test.local",
                subject="Reset",
                body="Body",
                use_tls=False,
                use_ssl=False,
            )

        self.assertEqual(1, mock_smtp.call_count)


if __name__ == "__main__":
    unittest.main()
