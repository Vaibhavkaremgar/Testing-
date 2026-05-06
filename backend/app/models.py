from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, Enum, Boolean, JSON, Index, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator
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
    INTERVIEW_FAILED = "INTERVIEW_FAILED"
    INTERVIEW_REVIEW = "INTERVIEW_REVIEW"
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


class ReviewStatusType(TypeDecorator):
    """
    Backward-compatible storage for review status.
    Accepts legacy enum names like 'UNASSIGNED' and canonical values like
    'unassigned', while always returning a ReviewStatus enum instance.
    """

    impl = String(50)
    cache_ok = True

    _name_lookup = {status.name.upper(): status for status in ReviewStatus}
    _value_lookup = {status.value.lower(): status for status in ReviewStatus}

    @classmethod
    def _coerce_to_enum(cls, value):
        if value is None:
            return None
        if isinstance(value, ReviewStatus):
            return value

        normalized = str(value).strip()
        if not normalized:
            return None

        by_name = cls._name_lookup.get(normalized.upper())
        if by_name is not None:
            return by_name

        by_value = cls._value_lookup.get(normalized.lower())
        if by_value is not None:
            return by_value

        raise ValueError(f"Unsupported review status: {value}")

    def process_bind_param(self, value, dialect):
        enum_value = self._coerce_to_enum(value)
        return enum_value.value if enum_value is not None else None

    def process_result_value(self, value, dialect):
        enum_value = self._coerce_to_enum(value)
        return enum_value if enum_value is not None else ReviewStatus.UNASSIGNED


class TransactionType(str, enum.Enum):
    CREDIT = "credit"
    DEBIT = "debit"


class NotificationDeliveryStatus(str, enum.Enum):
    PENDING = "pending"
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"


class WorkflowTokenType(str, enum.Enum):
    SLOT_SELECTION = "slot_selection"
    INTERVIEW_ACCESS = "interview_access"


class Agency(Base):
    __tablename__ = "agencies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    subscriptions = relationship("Subscription", back_populates="agency")
    wallet = relationship("Wallet", back_populates="agency", uselist=False)


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
    __table_args__ = (
        Index("idx_job_descriptions_agency_id_is_active", "agency_id", "is_active"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=True, index=True)
    job_id = Column(String(50), unique=True, index=True)
    title = Column(String(255), nullable=False)
    company_name = Column(String(255))
    company_website_url = Column(String(500))
    company_logo_url = Column(String(1000))
    department = Column(String(255))
    industry = Column(String(255))
    location = Column(String(255))
    city = Column(String(120))
    state = Column(String(120))
    country = Column(String(120))
    employment_type = Column(String(100))
    experience_required = Column(String(100))
    salary_range = Column(String(100))
    category = Column(String(150))
    remote = Column(Boolean, default=False, nullable=False)
    vacancies = Column(Integer, default=1)
    min_passing_score = Column(Integer, default=60)
    description = Column(Text)
    requirements = Column(Text)
    responsibilities = Column(Text)
    skills = Column(JSON)
    interview_questions = Column(JSON)
    is_active = Column(Boolean, default=True, index=True)
    status = Column(String(50), default='open')
    valid_through = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    candidates = relationship("Candidate", back_populates="job")
    applications = relationship(
        "JobApplication",
        back_populates="job",
        cascade="all, delete-orphan",
    )
    portal_mappings = relationship(
        "JobPortalMapping",
        back_populates="job",
        cascade="all, delete-orphan",
    )


class JobApplication(Base):
    __tablename__ = "job_applications"
    __table_args__ = (
        Index("idx_job_applications_job_id_created_at", "job_id", "created_at"),
        Index("idx_job_applications_email", "email"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("job_descriptions.id", ondelete="CASCADE"), nullable=False)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    phone = Column(String(50))
    original_filename = Column(String(255))
    stored_filename = Column(String(255))
    resume_url = Column(String(1000))
    cover_letter = Column(Text)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    job = relationship("JobDescription", back_populates="applications")


class Candidate(Base):
    __tablename__ = "candidates"
    __table_args__ = (
        Index("idx_candidates_agency_id_job_id", "agency_id", "job_id"),
        Index("idx_candidates_agency_id_stage", "agency_id", "stage"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=True, index=True)
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
    stage = Column(Enum(CandidateStage), default=CandidateStage.APPLIED, index=True)
    stage_updated_at = Column(DateTime(timezone=True), server_default=func.now())
    stage_entered_at = Column(DateTime(timezone=True), server_default=func.now())
    applied_at = Column(DateTime(timezone=True), server_default=func.now())

    # Source and decline tracking
    source = Column(String(100))
    decline_reason = Column(Text)
    offer_status = Column(String(50))
    internal_notes = Column(Text)

    # Resume review assignment
    assigned_to_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    review_status = Column(ReviewStatusType(), default=ReviewStatus.UNASSIGNED.value)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Google Sheets sync
    synced_to_sheets = Column(Boolean, default=False)
    summary = Column(Text, nullable=True)
    predefined_questions = Column(Text, nullable=True)

    # Relationships
    job_id = Column(UUID(as_uuid=True), ForeignKey("job_descriptions.id"), index=True)
    job = relationship("JobDescription", back_populates="candidates")

    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_by_user = relationship("User", back_populates="candidates", foreign_keys=[created_by])

    interviews = relationship("Interview", back_populates="candidate")

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class Interview(Base):
    __tablename__ = "interviews"
    __table_args__ = (
        Index("idx_interviews_agency_id_status", "agency_id", "status"),
        Index("idx_interviews_candidate_id_scheduled_at", "candidate_id", "scheduled_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=True, index=True)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.id"), nullable=False, index=True)
    candidate = relationship("Candidate", back_populates="interviews")

    interview_type = Column(String(100))
    scheduled_at = Column(DateTime(timezone=True), index=True)
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
    status = Column(String(50), default="scheduled", index=True)
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
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=True, index=True)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    name = Column(String(255), nullable=False)
    status = Column(String(100), nullable=False, index=True)
    subject = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    template_type = Column(String(100), nullable=True)
    variables = Column(JSON)
    description = Column(Text, nullable=True)
    is_html = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    is_selected = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
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
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=True, index=True)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.id"), nullable=False)
    template_id = Column(Integer, ForeignKey("email_templates.id"), nullable=True)
    candidate_name = Column(String(255))
    candidate_email = Column(String(255))
    email_type = Column(String(100))
    subject = Column(String(500), nullable=True)
    body = Column(Text, nullable=True)
    placeholder_payload = Column(JSON, nullable=True)
    workflow_token = Column(String(255), nullable=True)
    provider_message_id = Column(String(255), nullable=True)
    error_message = Column(Text, nullable=True)
    status = Column(String(50), default=NotificationDeliveryStatus.PENDING.value)
    sent_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class NotificationWorkflowToken(Base):
    __tablename__ = "notification_workflow_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=True, index=True)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.id"), nullable=True, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("job_descriptions.id"), nullable=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    token = Column(String(255), nullable=False, unique=True, index=True)
    token_type = Column(String(100), nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    consumed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class BookingLink(Base):
    __tablename__ = "booking_links"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    token = Column(String(255), nullable=False, unique=True, index=True, default=lambda: str(uuid.uuid4()))
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=True, index=True)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.id"), nullable=True, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("job_descriptions.id"), nullable=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    expires_at = Column(DateTime(timezone=True), server_default=text("NOW() + INTERVAL '72 hours'"))
    used = Column(Boolean, default=False)
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
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    widget_id = Column(Integer, ForeignKey("analytics_widgets.id"), nullable=False, index=True)
    position = Column(Integer, nullable=True)
    size = Column(String(50), nullable=True)
    is_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AgencyDiscount(Base):
    __tablename__ = "agency_discounts"

    id = Column(Integer, primary_key=True, index=True)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=False, unique=True)
    discount_type = Column(String(20), nullable=False)  # 'percentage' or 'amount'
    discount_value = Column(Float, nullable=False)
    currency = Column(String(10), default='USD')
    set_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    agency = relationship("Agency", foreign_keys=[agency_id])


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id = Column(Integer, primary_key=True, index=True)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    amount = Column(Integer, nullable=False)
    transaction_type = Column(Enum(TransactionType), nullable=False)
    description = Column(String(500))
    balance_after = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        Index("idx_subscriptions_agency_id_status", "agency_id", "status"),
        Index("idx_subscriptions_user_id_created_at", "user_id", "created_at"),
        Index("idx_subscriptions_expires_at", "expires_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("plans.id"), nullable=True, index=True)
    status = Column(String(50), nullable=True, default="active", index=True)
    plan_name = Column(String(50), nullable=False)
    billing_type = Column(String(20), nullable=False)
    price_per_user = Column(Float, nullable=True)
    total_price = Column(Float, nullable=True)
    interview_credits_total = Column(Integer, nullable=True)
    interview_credits_used = Column(Integer, default=0, nullable=False)
    max_job_posts = Column(Integer, nullable=True)
    used_job_posts = Column(Integer, default=0, nullable=False)
    max_users = Column(Integer, nullable=True)
    current_users = Column(Integer, default=0, nullable=False)
    resume_scoring_limit = Column(Integer, nullable=True)
    resume_scoring_used = Column(Integer, default=0, nullable=False)
    is_unlimited_resume_scoring = Column(Boolean, default=False, nullable=False)
    is_unlimited_jobs = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    cycle_anchor_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_monthly_reset_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    agency = relationship("Agency", back_populates="subscriptions", foreign_keys=[agency_id])
    user = relationship("User", foreign_keys=[user_id])
    plan = relationship("Plan", foreign_keys=[plan_id])
    wallet = relationship("Wallet", back_populates="subscription", uselist=False)
    usage_logs = relationship("UsageLog", back_populates="subscription")


class Plan(Base):
    __tablename__ = "plans"
    __table_args__ = (
        Index("idx_plans_name_duration", "name", "duration"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String(100), nullable=False, index=True)
    price = Column(Float, nullable=True)
    duration = Column(String(20), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    limits = relationship("PlanLimit", back_populates="plan")
    subscriptions = relationship("Subscription", back_populates="plan")


class PlanLimit(Base):
    __tablename__ = "plan_limits"
    __table_args__ = (
        UniqueConstraint("plan_id", "feature_name", name="uq_plan_limits_plan_feature"),
        Index("idx_plan_limits_plan_id", "plan_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("plans.id"), nullable=False)
    feature_name = Column(String(100), nullable=False, index=True)
    total_limit = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    plan = relationship("Plan", foreign_keys=[plan_id])


class Wallet(Base):
    __tablename__ = "wallets"
    __table_args__ = (
        UniqueConstraint("agency_id", name="uq_wallets_agency_id"),
        UniqueConstraint("subscription_id", name="uq_wallets_subscription_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=False, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False, index=True)

    interview_total = Column(Integer, nullable=True)
    interview_used = Column(Integer, default=0, nullable=False)
    interview_remaining = Column(Integer, nullable=True)
    is_interview_unlimited = Column(Boolean, default=False, nullable=False)

    resume_total = Column(Integer, nullable=True)
    resume_used = Column(Integer, default=0, nullable=False)
    resume_remaining = Column(Integer, nullable=True)
    is_resume_unlimited = Column(Boolean, default=False, nullable=False)

    job_post_total = Column(Integer, nullable=True)
    job_post_used = Column(Integer, default=0, nullable=False)
    job_post_remaining = Column(Integer, nullable=True)
    is_job_post_unlimited = Column(Boolean, default=False, nullable=False)

    user_seat_total = Column(Integer, nullable=True)
    user_seat_used = Column(Integer, default=0, nullable=False)
    user_seat_remaining = Column(Integer, nullable=True)
    is_user_seat_unlimited = Column(Boolean, default=False, nullable=False)

    last_reset_date = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    agency = relationship("Agency", back_populates="wallet", foreign_keys=[agency_id])
    subscription = relationship("Subscription", back_populates="wallet", foreign_keys=[subscription_id])
    usage_logs = relationship("UsageLog", back_populates="wallet")


class UsageLog(Base):
    __tablename__ = "usage_logs"
    __table_args__ = (
        Index("idx_usage_logs_agency_id_created_at", "agency_id", "created_at"),
        Index("idx_usage_logs_feature_name_created_at", "feature_name", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=False, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False, index=True)
    wallet_id = Column(Integer, ForeignKey("wallets.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    feature_name = Column(String(100), nullable=False, index=True)
    action = Column(String(50), nullable=False, default="consume")
    amount = Column(Integer, nullable=False, default=1)
    before_used = Column(Integer, nullable=True)
    after_used = Column(Integer, nullable=True)
    before_remaining = Column(Integer, nullable=True)
    after_remaining = Column(Integer, nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    subscription = relationship("Subscription", back_populates="usage_logs", foreign_keys=[subscription_id])
    wallet = relationship("Wallet", back_populates="usage_logs", foreign_keys=[wallet_id])
    user = relationship("User", foreign_keys=[user_id])


class UsageTracking(Base):
    __tablename__ = "usage_tracking"
    __table_args__ = (
        UniqueConstraint("user_id", "feature_name", name="uq_usage_tracking_user_feature"),
        Index("idx_usage_tracking_user_id", "user_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    feature_name = Column(String(100), nullable=False, index=True)
    used_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", foreign_keys=[user_id])


class JobPortal(Base):
    __tablename__ = "job_portals"
    __table_args__ = (
        Index("idx_job_portals_enabled", "is_enabled"),
        UniqueConstraint("portal_name", name="uq_job_portals_portal_name"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    portal_name = Column(String(100), nullable=False)
    is_enabled = Column(Boolean, default=True, nullable=False)
    feed_url = Column(String(500), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class JobDistributionLog(Base):
    __tablename__ = "job_distribution_logs"
    __table_args__ = (
        Index("idx_job_distribution_logs_job_id", "job_id"),
        Index("idx_job_distribution_logs_portal_status", "portal_name", "status"),
        Index("idx_job_distribution_logs_posted_at", "posted_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), nullable=True)
    portal_name = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False)
    message = Column(Text, nullable=True)
    posted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class JobPortalMapping(Base):
    __tablename__ = "job_portal_mapping"
    __table_args__ = (
        UniqueConstraint("job_id", "portal_name", name="uq_job_portal_mapping_job_portal"),
        Index("idx_job_portal_mapping_portal_name", "portal_name"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("job_descriptions.id", ondelete="CASCADE"), nullable=False)
    portal_name = Column(String(100), nullable=False)

    job = relationship("JobDescription", back_populates="portal_mappings")


class FeedAccessLog(Base):
    __tablename__ = "feed_access_logs"
    __table_args__ = (
        Index("idx_feed_access_logs_portal_accessed_at", "portal_name", "accessed_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    portal_name = Column(String(100), nullable=False)
    ip_address = Column(String(255))
    user_agent = Column(String(1000))
    accessed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
