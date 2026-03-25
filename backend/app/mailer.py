from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from app.config import settings


def is_email_configured() -> bool:
    return bool(settings.SENDGRID_API_KEY and settings.FROM_EMAIL)


def send_html_email(*, to_email: str, subject: str, html_content: str) -> str:
    if not is_email_configured():
        raise RuntimeError("SendGrid email is not configured")

    mail_message = Mail(
        from_email=(settings.FROM_EMAIL, settings.FROM_NAME),
        to_emails=to_email,
        subject=subject,
        html_content=html_content,
    )
    response = SendGridAPIClient(settings.SENDGRID_API_KEY).send(mail_message)
    return response.headers.get("X-Message-Id") if hasattr(response, "headers") else ""
