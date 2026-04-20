import smtplib
from email.message import EmailMessage


class EmailService:
    @staticmethod
    def _send_via_smtp(
        smtp_host: str,
        smtp_port: int,
        message: EmailMessage,
        username: str | None,
        password: str | None,
        use_tls: bool,
        use_ssl: bool,
    ) -> None:
        if use_ssl:
            with smtplib.SMTP_SSL(smtp_host, smtp_port) as smtp:
                if username and password:
                    smtp.login(username, password)
                smtp.send_message(message)
            return

        with smtplib.SMTP(smtp_host, smtp_port) as smtp:
            if use_tls:
                try:
                    smtp.starttls()
                except smtplib.SMTPNotSupportedError:
                    # Fallback für lokale SMTP-Server (z. B. MailHog),
                    # die STARTTLS nicht anbieten.
                    pass
            if username and password:
                smtp.login(username, password)
            smtp.send_message(message)

    @staticmethod
    def send_mail(
        smtp_host: str,
        smtp_port: int,
        sender: str,
        recipient: str,
        subject: str,
        body: str,
        username: str | None = None,
        password: str | None = None,
        use_tls: bool = True,
        use_ssl: bool = False,
    ) -> None:
        message = EmailMessage()
        message["From"] = sender
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)

        fallback_host = "mailhog"
        try:
            EmailService._send_via_smtp(
                smtp_host=smtp_host,
                smtp_port=smtp_port,
                message=message,
                username=username,
                password=password,
                use_tls=use_tls,
                use_ssl=use_ssl,
            )
        except ConnectionRefusedError:
            if smtp_host != "localhost":
                raise
            EmailService._send_via_smtp(
                smtp_host=fallback_host,
                smtp_port=smtp_port,
                message=message,
                username=username,
                password=password,
                use_tls=use_tls,
                use_ssl=use_ssl,
            )
