from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, Enum, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum
import uuid


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    RECRUITER = "recruiter"
    HIRING_MANAGER = "hiring_manager"
    VIEWER = "viewer"


class CandidateStage(str, enum.Enum):
    APPLIED = "APPLIED"
    SHORTLISTED = "SHORTLISTED"
    RESUME_REJECTED = "RESUME_REJECTED"
    REVIEW = "REVIEW"
    INTERVIEW_SCHEDULED = "INTERVIEW_SCHEDULED"
    INTERVIEW_RESCHEDULED = "INTERVIEW_RESCHEDULED"
    INTERVIEWED = "INTERVIEWED"
    NO_SHOW = "NO_SHOW"
    SELECTED = "SELECTED"
    REJECTED = "REJECTED"


class ParsingStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ReviewStatus(str, enum.Enum):
    UNASSIGNED = "unassigned"
    PENDING = "pending"
    INTERVIEW_INVITED = "interview_invited"
    REJECTED = "rejected"


class TransactionType(str, enum.Enum):
    CREDIT = "credit"
    DEBIT = "debit"


class Agency(Base):
    __tablename__ = "agencies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(Enum(UserRole, values_callable=lambda x: [e.value for e in x], create_type=False), default=UserRole.RECRUITER)
    phone = Column(String(50))
    department = Column(String(255))
    bio = Column(Text)
    avatar_url = Column(String(500))
    is_active = Column(Boolean, default=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    wallet_balance = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    agency = relationship("Agency", foreign_keys=[agency_id])
    candidates = relationship("Candidate", back_populates="created_by_user", foreign_keys="[Candidate.created_by]")


class JobDescription(Base):
    __tablename__ = "job_descriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=True)
    job_id = Column(String(50), unique=True, index=True)
    title = Column(String(255), nullable=False)
    company_name = Column(String(255))
    department = Column(String(255))
    location = Column(String(255))
    employment_type = Column(String(100))
    experience_required = Column(String(100))
    salary_range = Column(String(100))
    vacancies = Column(Integer, default=1)
    min_passing_score = Column(Integer, default=60)
    description = Column(Text)
    requirements = Column(Text)
    responsibilities = Column(Text)
    skills = Column(JSON)
    interview_questions = Column(JSON)
    is_active = Column(Boolean, default=True)
    status = Column(String(50), default='open')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    candidates = relationship("Candidate", back_populates="job")


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=True)
    candidate_id = Column(String(50), unique=True, index=True)
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
    resume_score = Column(Float)
    score_threshold = Column(Float)
    skills = Column(JSON)
    education = Column(JSON)
    work_experience = Column(JSON)

    # Pipeline
    stage = Column(Enum(CandidateStage), default=CandidateStage.APPLIED)
    stage_updated_at = Column(DateTime(timezone=True), server_default=func.now())
    stage_entered_at = Column(DateTime(timezone=True), server_default=func.now())
    applied_at = Column(DateTime(timezone=True), server_default=func.now())

    # Source and decline tracking
    source = Column(String(100))
    decline_reason = Column(Text)
    offer_status = Column(String(50))
    internal_notes = Column(Text)

    # Resume review assignment
    assigned_to_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    review_status = Column(Enum(ReviewStatus), default=ReviewStatus.UNASSIGNED)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Google Sheets sync
    synced_to_sheets = Column(Boolean, default=False)
    summary = Column(Text, nullable=True)
    predefined_questions = Column(Text, nullable=True)

    # Relationships
    job_id = Column(UUID(as_uuid=True), ForeignKey("job_descriptions.id"))
    job = relationship("JobDescription", back_populates="candidates")

    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_by_user = relationship("User", back_populates="candidates", foreign_keys=[created_by])

    interviews = relationship("Interview", back_populates="candidate")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class Interview(Base):
    __tablename__ = "interviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=True)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.id"), nullable=False)
    candidate = relationship("Candidate", back_populates="interviews")

    interview_type = Column(String(100))
    scheduled_at = Column(DateTime(timezone=True))
    duration_minutes = Column(Integer)
    meeting_link = Column(String(500))

    # Async Interview
    is_async = Column(Boolean, default=False)
    async_link = Column(String(500))
    async_token = Column(String(255), unique=True)
    async_expires_at = Column(DateTime(timezone=True))
    async_started_at = Column(DateTime(timezone=True))
    async_completed_at = Column(DateTime(timezone=True))
    async_answers = Column(JSON)

    # Interview Results
    status = Column(String(50), default="scheduled")
    video_url = Column(String(500))
    transcript = Column(Text)
    ai_summary = Column(Text)
    interview_score = Column(Float)
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
    template_type = Column(String(100))
    variables = Column(JSON)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    agency_id = Column(Integer, ForeignKey("agencies.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String(255), nullable=False)
    entity_type = Column(String(100))
    entity_id = Column(Integer)
    details = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Client(Base):
    __tablename__ = "clients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=True)
    company_name = Column(String(255), nullable=False)
    industry = Column(String(255))
    contact_person = Column(String(255))
    contact_email = Column(String(255))
    contact_phone = Column(String(50))
    total_positions = Column(Integer, default=0)
    positions_filled = Column(Integer, default=0)
    positions_open = Column(Integer, default=0)
    avg_time_to_hire = Column(Float)
    retention_rate = Column(Float)
    acceptance_rate = Column(Float)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class EmailCommunication(Base):
    __tablename__ = "email_communications"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.id"), nullable=False)
    candidate_name = Column(String(255))
    candidate_email = Column(String(255))
    email_type = Column(String(100))
    status = Column(String(50), default="pending")
    sent_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AnalyticsWidget(Base):
    __tablename__ = "analytics_widgets"

    id = Column(Integer, primary_key=True, index=True)
    widget_name = Column(String(255), nullable=False)
    metric_key = Column(String(100), nullable=False, index=True)
    role_access = Column(String(255), nullable=True)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UserDashboardPreference(Base):
    __tablename__ = "user_dashboard_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    widget_id = Column(Integer, ForeignKey("analytics_widgets.id"), nullable=False, index=True)
    position = Column(Integer, nullable=True)
    size = Column(String(50), nullable=True)
    is_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id = Column(Integer, primary_key=True, index=True)
    agency_id = Column(Integer, ForeignKey("agencies.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Integer, nullable=False)
    transaction_type = Column(Enum(TransactionType), nullable=False)
    description = Column(String(500))
    balance_after = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
