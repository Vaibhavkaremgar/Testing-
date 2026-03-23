from pydantic import BaseModel, EmailStr
from typing import Optional, List, Any
from datetime import datetime
from uuid import UUID
from app.models import UserRole, CandidateStage, ParsingStatus, ReviewStatus

# Agency Schemas
class AgencyCreate(BaseModel):
    name: str
    slug: str
    is_active: bool = True

class AgencyWithAdminCreate(BaseModel):
    name: str
    slug: str
    is_active: bool = True
    admin_full_name: str
    admin_email: EmailStr
    admin_password: str

class AgencyUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    is_active: Optional[bool] = None

class AgencyResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

# Auth Schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None
    agency_id: Optional[UUID] = None

class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    role: UserRole = UserRole.RECRUITER
    phone: Optional[str] = None
    department: Optional[str] = None
    bio: Optional[str] = None
    agency_id: Optional[UUID] = None

class UserCreate(UserBase):
    password: str
    agency_id: Optional[UUID] = None

class UserResponse(UserBase):
    id: UUID
    is_active: bool
    avatar_url: Optional[str] = None
    last_login_at: Optional[datetime] = None
    is_online: Optional[bool] = False
    agency_name: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    bio: Optional[str] = None
    email: Optional[EmailStr] = None

class AdminUserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class PasswordUpdate(BaseModel):
    current_password: str
    new_password: str

# Job Description Schemas
class JobDescriptionBase(BaseModel):
    title: str
    job_id: Optional[str] = None
    company_name: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    employment_type: Optional[str] = None
    experience_required: Optional[str] = None
    salary_range: Optional[str] = None
    vacancies: Optional[int] = 1
    min_passing_score: Optional[int] = 60
    description: Optional[str] = None
    requirements: Optional[str] = None
    responsibilities: Optional[str] = None
    skills: Optional[List[str]] = None
    interview_questions: Optional[List[Any]] = None

class JobDescriptionCreate(JobDescriptionBase):
    pass

class JobDescriptionUpdate(JobDescriptionBase):
    title: Optional[str] = None
    is_active: Optional[bool] = None

class JobDescriptionResponse(JobDescriptionBase):
    id: UUID
    job_id: Optional[str] = None
    is_active: bool
    vacancies: int
    created_at: datetime
    candidate_count: Optional[int] = 0
    
    class Config:
        from_attributes = True

# Candidate Schemas
class CandidateBase(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    current_company: Optional[str] = None
    current_role: Optional[str] = None
    experience_years: Optional[float] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None

class CandidateCreate(CandidateBase):
    job_id: Optional[UUID] = None

class CandidateUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    current_company: Optional[str] = None
    current_role: Optional[str] = None
    experience_years: Optional[float] = None
    location: Optional[str] = None
    stage: Optional[CandidateStage] = None
    job_id: Optional[UUID] = None

class CandidateAssign(BaseModel):
    assigned_to_user_id: UUID

class CandidateReview(BaseModel):
    action: str  # "interview" or "reject"

class CandidateResponse(CandidateBase):
    id: UUID
    resume_file_path: Optional[str] = None
    resume_text: Optional[str] = None
    parsing_status: ParsingStatus
    resume_score: Optional[float] = None
    score_threshold: Optional[float] = None
    skills: Optional[List[str]] = None
    education: Optional[List[Any]] = None
    work_experience: Optional[List[Any]] = None
    stage: CandidateStage
    stage_updated_at: datetime
    stage_entered_at: Optional[datetime] = None
    applied_at: Optional[datetime] = None
    job_id: Optional[UUID] = None
    job_title: Optional[str] = None
    summary: Optional[str] = None
    predefined_questions: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class CandidateStageUpdate(BaseModel):
    stage: CandidateStage

# Interview Schemas
class InterviewBase(BaseModel):
    interview_type: str
    scheduled_at: datetime
    duration_minutes: int = 60
    meeting_link: Optional[str] = None

class InterviewCreate(InterviewBase):
    candidate_id: UUID

class InterviewUpdate(BaseModel):
    interview_type: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    meeting_link: Optional[str] = None
    status: Optional[str] = None
    video_url: Optional[str] = None
    transcript: Optional[str] = None
    ai_summary: Optional[str] = None
    interview_score: Optional[float] = None
    feedback: Optional[str] = None
    interviewer_notes: Optional[str] = None
    technical_score: Optional[float] = None
    communication_score: Optional[float] = None
    culture_fit_score: Optional[float] = None

class InterviewResultsUpdate(BaseModel):
    video_url: Optional[str] = None
    transcript: Optional[str] = None
    ai_summary: Optional[str] = None
    interview_score: Optional[float] = None
    technical_score: Optional[float] = None
    communication_score: Optional[float] = None
    culture_fit_score: Optional[float] = None
    feedback: Optional[str] = None

class InterviewResponse(InterviewBase):
    id: UUID
    candidate_id: UUID
    candidate_name: Optional[str] = None
    status: str
    video_url: Optional[str] = None
    transcript: Optional[str] = None
    ai_summary: Optional[str] = None
    interview_score: Optional[float] = None
    feedback: Optional[str] = None
    technical_score: Optional[float] = None
    communication_score: Optional[float] = None
    culture_fit_score: Optional[float] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

# Email Template Schemas
class EmailTemplateBase(BaseModel):
    name: str
    status: str
    subject: str
    body: str
    template_type: Optional[str] = None
    variables: Optional[List[str]] = None
    description: Optional[str] = None
    is_html: bool = True

class EmailTemplateCreate(EmailTemplateBase):
    agency_id: Optional[UUID] = None
    is_default: bool = False

class EmailTemplateUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    template_type: Optional[str] = None
    variables: Optional[List[str]] = None
    description: Optional[str] = None
    is_html: Optional[bool] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None

class EmailTemplateResponse(EmailTemplateBase):
    id: int
    agency_id: Optional[UUID] = None
    is_default: bool
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class EmailTemplatePreviewRequest(BaseModel):
    agency_id: Optional[UUID] = None
    status: str
    candidate_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    payload: Optional[dict[str, Any]] = None

class EmailTemplatePreviewResponse(BaseModel):
    subject: str
    body: str
    payload: dict[str, Any]
    template_id: Optional[int] = None
    used_default_template: bool = False

class NotificationEventRequest(BaseModel):
    candidate_id: UUID
    status: str
    user_id: Optional[UUID] = None
    payload: Optional[dict[str, Any]] = None

class NotificationEventResponse(BaseModel):
    queued: bool
    candidate_id: UUID
    status: str
    template_id: Optional[int] = None
    communication_id: Optional[int] = None
    workflow_token: Optional[str] = None

class SlotSelectionSubmitRequest(BaseModel):
    interview_date: str
    interview_time: str
    timezone: Optional[str] = None
    notes: Optional[str] = None

class WorkflowTokenResolveResponse(BaseModel):
    token_type: str
    payload: dict[str, Any]
    expires_at: Optional[datetime] = None
    consumed_at: Optional[datetime] = None
    is_active: bool

# Analytics Schemas
class DashboardStats(BaseModel):
    total_candidates: int
    shortlisted: int
    resume_rejected: int
    rejected: int
    interviews_scheduled: int
    selected: int
    avg_resume_score: float
    avg_interview_score: float

class PipelineStats(BaseModel):
    stage: str
    count: int

class HiringFunnelData(BaseModel):
    stage: str
    count: int
    percentage: float

class TimeToHireData(BaseModel):
    month: str
    avg_days: float

class SkillHeatmapData(BaseModel):
    skill: str
    count: int
    avg_score: float

class ScoreDistribution(BaseModel):
    range: str
    count: int

# Client Schemas
class ClientBase(BaseModel):
    company_name: str
    industry: Optional[str] = None
    contact_person: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    total_positions: Optional[int] = 0
    positions_filled: Optional[int] = 0
    positions_open: Optional[int] = 0
    avg_time_to_hire: Optional[float] = None
    retention_rate: Optional[float] = None
    acceptance_rate: Optional[float] = None

class ClientCreate(ClientBase):
    pass

class ClientUpdate(ClientBase):
    company_name: Optional[str] = None
    is_active: Optional[bool] = None

class ClientResponse(ClientBase):
    id: UUID
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class ClientStats(BaseModel):
    total_clients: int
    active_clients: int
    total_positions: int
    open_positions: int
    filled_positions: int

# Communication Schemas
class EmailCommunicationCreate(BaseModel):
    candidate_id: UUID
    email_type: str

class EmailCommunicationUpdate(BaseModel):
    status: Optional[str] = None

class EmailCommunicationResponse(BaseModel):
    id: int
    candidate_id: UUID
    agency_id: Optional[UUID] = None
    template_id: Optional[int] = None
    candidate_name: Optional[str] = None
    candidate_email: Optional[str] = None
    email_type: str
    subject: Optional[str] = None
    body: Optional[str] = None
    placeholder_payload: Optional[dict[str, Any]] = None
    workflow_token: Optional[str] = None
    provider_message_id: Optional[str] = None
    error_message: Optional[str] = None
    status: str
    sent_at: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True
