import resend

from app.config import settings

resend.api_key = settings.RESEND_API_KEY


def is_email_configured() -> bool:
    return bool(settings.RESEND_API_KEY and settings.FROM_EMAIL)


def send_html_email(*, to_email: str, subject: str, html_content: str) -> str:
    if not is_email_configured():
        raise RuntimeError("Resend email API is not configured")

    print(
        f"Resend send starting: to={to_email}, "
        f"from={settings.FROM_EMAIL}, timeout={settings.SMTP_TIMEOUT_SECONDS}s"
    )

    response = resend.Emails.send(
        {
            "from": f"{settings.FROM_NAME} <{settings.FROM_EMAIL}>",
            "to": [to_email],
            "subject": subject,
            "html": html_content,
        }
    )
    message_id = str(response.get("id", "")) if isinstance(response, dict) else ""

    print(f"Resend send completed: to={to_email}, message_id={message_id}")
    return message_id
