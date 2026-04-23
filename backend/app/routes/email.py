from datetime import datetime
from html import escape

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from app.auth import get_current_active_user
from app.database import get_db
from app.mailer import is_email_configured, send_html_email
from app.models import Candidate, EmailCommunication, User

router = APIRouter(prefix="/email", tags=["Email"])
SUPPORT_EMAIL = "info@pontis.one"

class SendEmailRequest(BaseModel):
    candidate_id: int
    email_type: str  # "interview_invitation" or "rejection"
    subject: str
    body: str


class SupportEmailRequest(BaseModel):
    full_name: str
    email_address: EmailStr
    mobile_number: str
    company_name: str
    subject: str
    message: str

@router.post("/send")
async def send_email(
    request: SendEmailRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Send email to candidate and log it in communications
    """
    # Get candidate
    candidate = db.query(Candidate).filter(Candidate.id == request.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # For now, simulate email sending (you can integrate real SMTP later)
    email_status = "sent"
    error_message = None
    
    try:
        # TODO: Add real email sending logic here
        # Example SMTP code (commented out):
        # msg = MIMEMultipart()
        # msg['From'] = "your-email@example.com"
        # msg['To'] = candidate.email
        # msg['Subject'] = request.subject
        # msg.attach(MIMEText(request.body, 'plain'))
        # 
        # server = smtplib.SMTP('smtp.gmail.com', 587)
        # server.starttls()
        # server.login("your-email@example.com", "your-password")
        # server.send_message(msg)
        # server.quit()
        
        # Simulate successful send
        print(f"Email sent to {candidate.email}: {request.subject}")
        
    except Exception as e:
        email_status = "failed"
        error_message = str(e)
        print(f"Failed to send email: {e}")
    
    # Log email communication
    email_comm = EmailCommunication(
        candidate_id=candidate.id,
        candidate_name=candidate.name,
        candidate_email=candidate.email,
        email_type=request.email_type,
        status=email_status,
        sent_at=datetime.utcnow() if email_status == "sent" else None
    )
    
    db.add(email_comm)
    db.commit()
    
    return {
        "success": email_status == "sent",
        "status": email_status,
        "message": f"Email {email_status}" if email_status == "sent" else f"Email failed: {error_message}",
        "candidate_email": candidate.email
    }


@router.post("/support")
async def send_support_email(
    request: SupportEmailRequest,
    current_user: User = Depends(get_current_active_user),
):
    """
    Send support request email to the Pontis support inbox.
    """
    if not is_email_configured():
        raise HTTPException(
            status_code=500,
            detail=(
                "Email service is not configured. Set RESEND_API_KEY "
                "(or SENDGRID_API_KEY for fallback), FROM_EMAIL, and FROM_NAME."
            ),
        )

    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 640px; margin: 0 auto; padding: 24px;">
            <h2 style="margin: 0 0 16px;">New support request</h2>
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                <tr><td style="padding: 8px 0; font-weight: 600; width: 180px;">Full Name</td><td style="padding: 8px 0;">{escape(request.full_name.strip())}</td></tr>
                <tr><td style="padding: 8px 0; font-weight: 600;">Email Address</td><td style="padding: 8px 0;">{escape(request.email_address.strip())}</td></tr>
                <tr><td style="padding: 8px 0; font-weight: 600;">Mobile Number</td><td style="padding: 8px 0;">{escape(request.mobile_number.strip())}</td></tr>
                <tr><td style="padding: 8px 0; font-weight: 600;">Company</td><td style="padding: 8px 0;">{escape(request.company_name.strip())}</td></tr>
                <tr><td style="padding: 8px 0; font-weight: 600;">Submitted By</td><td style="padding: 8px 0;">{escape(current_user.email or "")}</td></tr>
            </table>
            <div style="padding: 16px; border: 1px solid #e2e8f0; border-radius: 12px; background: #f8fafc;">
                <div style="font-weight: 600; margin-bottom: 8px;">Message</div>
                <div>{escape(request.message.strip()).replace(chr(10), '<br>')}</div>
            </div>
        </div>
    </body>
    </html>
    """

    try:
        provider_message_id = send_html_email(
            to_email=SUPPORT_EMAIL,
            subject=request.subject.strip(),
            html_content=html_body,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to send support email: {exc}") from exc

    return {
        "success": True,
        "message": f"Support email sent to {SUPPORT_EMAIL}",
        "provider_message_id": provider_message_id,
    }
