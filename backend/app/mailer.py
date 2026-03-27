import requests

from app.config import settings


def is_email_configured() -> bool:
    return bool(settings.SENDGRID_API_KEY and settings.FROM_EMAIL)


def send_html_email(*, to_email: str, subject: str, html_content: str) -> str:
    if not is_email_configured():
        raise RuntimeError("SendGrid email API is not configured")

    print(
        f"SendGrid send starting: to={to_email}, "
        f"from={settings.FROM_EMAIL}, timeout={settings.SMTP_TIMEOUT_SECONDS}s"
    )

    response = requests.post(
        settings.SENDGRID_API_URL,
        headers={
            "Authorization": f"Bearer {settings.SENDGRID_API_KEY}",
            "content-type": "application/json",
        },
        json={
            "personalizations": [
                {
                    "to": [{"email": to_email}],
                    "subject": subject,
                }
            ],
            "from": {
                "email": settings.FROM_EMAIL,
                "name": settings.FROM_NAME,
            },
            "content": [
                {
                    "type": "text/html",
                    "value": html_content,
                }
            ],
        },
        timeout=settings.SMTP_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    message_id = response.headers.get("X-Message-Id", "")

    print(f"SendGrid send completed: to={to_email}, message_id={message_id}")
    return message_id
