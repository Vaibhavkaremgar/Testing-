import smtplib
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from app.config import settings


def is_email_configured() -> bool:
    return bool(
        settings.SMTP_HOST
        and settings.SMTP_PORT
        and settings.SMTP_USERNAME
        and settings.SMTP_PASSWORD
        and settings.FROM_EMAIL
    )


def send_html_email(*, to_email: str, subject: str, html_content: str) -> str:
    if not is_email_configured():
        raise RuntimeError("SMTP email is not configured")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((settings.FROM_NAME, settings.FROM_EMAIL))
    message["To"] = to_email
    message["Message-ID"] = make_msgid()
    message.set_content("This email requires an HTML-compatible email client.")
    message.add_alternative(html_content, subtype="html")

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as smtp:
        if settings.SMTP_USE_TLS:
            smtp.starttls()
        smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        smtp.send_message(message)

    return message["Message-ID"]
