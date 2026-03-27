from typing import Optional

import requests

from app.config import settings


def _normalized_provider() -> str:
    provider = (settings.EMAIL_PROVIDER or "").strip().lower()
    if provider in {"resend", "sendgrid"}:
        return provider
    if settings.RESEND_API_KEY:
        return "resend"
    if settings.SENDGRID_API_KEY:
        return "sendgrid"
    return ""


def get_email_provider() -> str:
    return _normalized_provider()


def is_email_configured() -> bool:
    return bool(get_email_provider() and settings.FROM_EMAIL)


def _send_with_resend(*, to_email: str, subject: str, html_content: str) -> str:
    response = requests.post(
        settings.RESEND_API_URL,
        headers={
            "Authorization": f"Bearer {settings.RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "from": f"{settings.FROM_NAME} <{settings.FROM_EMAIL}>",
            "to": [to_email],
            "subject": subject,
            "html": html_content,
        },
        timeout=settings.SMTP_TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    data = response.json() if response.content else {}
    return data.get("id", "")


def _send_with_sendgrid(*, to_email: str, subject: str, html_content: str) -> str:
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
    return response.headers.get("X-Message-Id", "")


def _build_missing_config_message(provider: Optional[str]) -> str:
    if provider == "resend":
        return "Resend email API is not configured"
    if provider == "sendgrid":
        return "SendGrid email API is not configured"
    return "Email service is not configured"


def send_html_email(*, to_email: str, subject: str, html_content: str) -> str:
    provider = get_email_provider()
    if not provider or not settings.FROM_EMAIL:
        raise RuntimeError(_build_missing_config_message(provider))

    print(
        f"Email send starting: provider={provider}, to={to_email}, "
        f"from={settings.FROM_EMAIL}, timeout={settings.SMTP_TIMEOUT_SECONDS}s"
    )

    if provider == "resend":
        if not settings.RESEND_API_KEY:
            raise RuntimeError(_build_missing_config_message(provider))
        message_id = _send_with_resend(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
        )
    elif provider == "sendgrid":
        if not settings.SENDGRID_API_KEY:
            raise RuntimeError(_build_missing_config_message(provider))
        message_id = _send_with_sendgrid(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
        )
    else:
        raise RuntimeError(_build_missing_config_message(provider))

    print(
        f"Email send completed: provider={provider}, "
        f"to={to_email}, message_id={message_id}"
    )
    return message_id
