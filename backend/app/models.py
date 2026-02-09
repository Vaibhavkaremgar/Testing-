from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, Enum, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    RECRUITER = "recruiter"
    HIRING_MANAGER = "hiring_manager"
    VIEWER = "viewer"

class CandidateStage(str, enum.Enum):
    UPLOADED = "uploaded"
    SHORTLISTED = "shortlisted"
    INTERVIEW_SCHEDULED = "interview_scheduled"
    INTERVIEW_RESCHEDULED = "interview_rescheduled"
    INTERVIEWED = "interviewed"
    NO_SHOW = "no_show"
    SELECTED = "selected"
    REJECTED = "rejected"

class ParsingStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.RECRUITER)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    candidates = relationship("Candidate", back_populates="created_by_user")

class JobDescription(Base):
    __tablename__ = "job_descriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(50), unique=True, index=True)  # Custom job ID
    title = Column(String(255), nullable=False)
    company_name = Column(String(255))  # Company name
    department = Column(String(255))
    location = Column(String(255))
    employment_type = Column(String(100))  # full-time, part-time, contract
    experience_required = Column(String(100))
    salary_range = Column(String(100))
    vacancies = Column(Integer, default=1)  # Number of open positions
    description = Column(Text)
    requirements = Column(Text)
    responsibilities = Column(Text)
    skills = Column(JSON)  # List of required skills
    is_active = Column(Boolean, default=True)
    status = Column(String(50), default='open')  # open, on_hold, filled
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    candidates = relationship("Candidate", back_populates="job")

class Candidate(Base):
    __tablename__ = "candidates"
    
    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(String(50), unique=True, index=True)  # Generated ID: first3letters+jobid
    name = Column(String(255), nullable=False)
    email = Column(String(255), index=True)
    phone = Column(String(50))
    current_company = Column(String(255))
    current_role = Column(String(255))
    experience_years = Column(Float)
    location = Column(String(255))
    linkedin_url = Column(String(500))
    
    # Resume info
    resume_file_path = Column(String(500))
    resume_text = Column(Text)
    parsing_status = Column(Enum(ParsingStatus), default=ParsingStatus.PENDING)
    resume_score = Column(Float)  # AI-generated score 0-100
    score_threshold = Column(Float)  # Threshold used when candidate was uploaded
    skills = Column(JSON)  # Extracted skills
    education = Column(JSON)  # Extracted education
    work_experience = Column(JSON)  # Extracted work experience
    
    # Pipeline
    stage = Column(Enum(CandidateStage), default=CandidateStage.UPLOADED)
    stage_updated_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Source and decline tracking
    source = Column(String(100))  # LinkedIn, Referral, Job Board, Career Site, etc.
    decline_reason = Column(Text)  # Reason for rejection
    offer_status = Column(String(50))  # made, accepted, declined
    
    # Google Sheets sync
    synced_to_sheets = Column(Boolean, default=False)
    summary = Column(Text)  # Summary from Google Sheets
    
    # Relationships
    job_id = Column(Integer, ForeignKey("job_descriptions.id"))
    job = relationship("JobDescription", back_populates="candidates")
    
    created_by = Column(Integer, ForeignKey("users.id"))
    created_by_user = relationship("User", back_populates="candidates")
    
    interviews = relationship("Interview", back_populates="candidate")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Interview(Base):
    __tablename__ = "interviews"
    
    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    candidate = relationship("Candidate", back_populates="interviews")
    
    interview_type = Column(String(100))  # screening, technical, hr, final
    scheduled_at = Column(DateTime(timezone=True))
    duration_minutes = Column(Integer)
    meeting_link = Column(String(500))
    
    # Interview Results
    status = Column(String(50), default="scheduled")  # scheduled, completed, cancelled
    video_url = Column(String(500))
    transcript = Column(Text)
    ai_summary = Column(Text)
    interview_score = Column(Float)  # 0-100
    feedback = Column(Text)
    interviewer_notes = Column(Text)
    
    # Scores breakdown
    technical_score = Column(Float)
    communication_score = Column(Float)
    culture_fit_score = Column(Float)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class EmailTemplate(Base):
    __tablename__ = "email_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    subject = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    template_type = Column(String(100))  # offer, rejection, interview_invite, etc.
    variables = Column(JSON)  # Available template variables
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class ActivityLog(Base):
    __tablename__ = "activity_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String(255), nullable=False)
    entity_type = Column(String(100))  # candidate, interview, job, etc.
    entity_id = Column(Integer)
    details = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Client(Base):
    __tablename__ = "clients"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    industry = Column(String(255))
    contact_person = Column(String(255))
    contact_email = Column(String(255))
    contact_phone = Column(String(50))
    total_positions = Column(Integer, default=0)
    positions_filled = Column(Integer, default=0)
    positions_open = Column(Integer, default=0)
    avg_time_to_hire = Column(Float)  # in days
    retention_rate = Column(Float)  # percentage
    acceptance_rate = Column(Float)  # percentage
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class EmailCommunication(Base):
    __tablename__ = "email_communications"
    
    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    candidate_name = Column(String(255))
    candidate_email = Column(String(255))
    email_type = Column(String(100))  # offer_letter, rejection, interview_invitation
    status = Column(String(50), default="pending")  # pending, sent, failed
    sent_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
