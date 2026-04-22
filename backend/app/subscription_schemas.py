from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SelectPlanRequest(BaseModel):
    user_id: UUID
    plan_name: Literal["starter", "growth", "enterprise"]
    billing_type: Literal["monthly", "yearly"]
    user_count: int = Field(..., gt=0)


class SubscriptionResponse(BaseModel):
    id: int
    user_id: UUID
    plan_name: str
    billing_type: str
    price_per_user: Optional[float] = None
    total_price: Optional[float] = None
    interview_credits_total: Optional[int] = None
    interview_credits_used: int
    max_job_posts: Optional[int] = None
    used_job_posts: int
    max_users: Optional[int] = None
    current_users: int
    resume_scoring_limit: Optional[int] = None
    resume_scoring_used: int
    is_unlimited_resume_scoring: bool
    is_unlimited_jobs: bool
    expires_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class ManagedUserCreate(BaseModel):
    email: str
    full_name: str
    password: str
    role: Literal["admin", "recruiter", "hiring_manager", "viewer"] = "recruiter"

