import smtplib
from email.message import EmailMessage


class EmailService:
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

        if use_ssl:
            with smtplib.SMTP_SSL(smtp_host, smtp_port) as smtp:
                if username and password:
                    smtp.login(username, password)
                smtp.send_message(message)
            return

        with smtplib.SMTP(smtp_host, smtp_port) as smtp:
            if use_tls:
                smtp.starttls()
            if username and password:
                smtp.login(username, password)
            smtp.send_message(message)
