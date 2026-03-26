import smtplib
from email.message import EmailMessage
from email.utils import make_msgid

# SendGrid implementation kept for now as commented reference.
# from sendgrid import SendGridAPIClient
# from sendgrid.helpers.mail import Mail

from app.config import settings


def is_email_configured() -> bool:
    return bool(settings.GMAIL_SENDER and settings.GMAIL_APP_PASSWORD)


def send_html_email(*, to_email: str, subject: str, html_content: str) -> str:
    if not is_email_configured():
        raise RuntimeError("Gmail SMTP is not configured")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{settings.FROM_NAME} <{settings.FROM_EMAIL or settings.GMAIL_SENDER}>"
    message["To"] = to_email
    message["Message-ID"] = make_msgid()
    message.set_content("This email requires HTML support.")
    message.add_alternative(html_content, subtype="html")

    print(
        f"SMTP send starting: to={to_email}, "
        f"from={settings.FROM_EMAIL or settings.GMAIL_SENDER}, timeout={settings.SMTP_TIMEOUT_SECONDS}s"
    )

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=settings.SMTP_TIMEOUT_SECONDS) as server:
        server.starttls()
        server.login(settings.GMAIL_SENDER, settings.GMAIL_APP_PASSWORD)
        server.send_message(message)

    print(f"SMTP send completed: to={to_email}")

    # SendGrid implementation kept for now as commented reference.
    # mail_message = Mail(
    #     from_email=(settings.FROM_EMAIL, settings.FROM_NAME),
    #     to_emails=to_email,
    #     subject=subject,
    #     html_content=html_content,
    # )
    # response = SendGridAPIClient(settings.SENDGRID_API_KEY).send(mail_message)
    # return response.headers.get("X-Message-Id") if hasattr(response, "headers") else ""

    return message["Message-ID"] or ""
