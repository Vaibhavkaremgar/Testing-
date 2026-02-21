from pydantic import BaseModel, EmailStr
from typing import Optional, List, Any
from datetime import datetime
from app.models import UserRole, CandidateStage, ParsingStatus

# Auth Schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    role: UserRole = UserRole.RECRUITER

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

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
    id: int
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
    job_id: Optional[int] = None

class CandidateUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    current_company: Optional[str] = None
    current_role: Optional[str] = None
    experience_years: Optional[float] = None
    location: Optional[str] = None
    stage: Optional[CandidateStage] = None
    job_id: Optional[int] = None

class CandidateResponse(CandidateBase):
    id: int
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
    job_id: Optional[int] = None
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
    candidate_id: int

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

class InterviewResponse(InterviewBase):
    id: int
    candidate_id: int
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
    subject: str
    body: str
    template_type: str
    variables: Optional[List[str]] = None

class EmailTemplateCreate(EmailTemplateBase):
    pass

class EmailTemplateUpdate(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    template_type: Optional[str] = None
    variables: Optional[List[str]] = None
    is_active: Optional[bool] = None

class EmailTemplateResponse(EmailTemplateBase):
    id: int
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

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
    name: str
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
    name: Optional[str] = None
    is_active: Optional[bool] = None

class ClientResponse(ClientBase):
    id: int
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
    candidate_id: int
    email_type: str

class EmailCommunicationUpdate(BaseModel):
    status: Optional[str] = None

class EmailCommunicationResponse(BaseModel):
    id: int
    candidate_id: int
    candidate_name: Optional[str] = None
    candidate_email: Optional[str] = None
    email_type: str
    status: str
    sent_at: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True
