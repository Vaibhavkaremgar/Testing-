from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from datetime import datetime
from app.database import get_db
from app.models import Candidate, EmailCommunication, User
from app.auth import get_current_active_user
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

router = APIRouter(prefix="/email", tags=["Email"])

class SendEmailRequest(BaseModel):
    candidate_id: int
    email_type: str  # "interview_invitation" or "rejection"
    subject: str
    body: str

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
