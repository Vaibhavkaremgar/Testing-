from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, model_validator


PlanName = Literal["starter", "growth", "custom"]
BillingType = Literal["monthly", "yearly"]


class CustomPlanConfig(BaseModel):
    price_per_user: Optional[float] = Field(default=None, ge=0)
    interview_credits: Optional[int] = Field(default=None, ge=0)
    resume_scans: Optional[int] = Field(default=None, ge=0)
    job_postings: Optional[int] = Field(default=None, ge=0)
    user_seats: Optional[int] = Field(default=None, ge=0)
    unlimited_interviews: bool = False
    unlimited_resume_scans: bool = False
    unlimited_job_postings: bool = False
    unlimited_user_seats: bool = False


class SubscribeRequest(BaseModel):
    organization_id: Optional[UUID] = None
    plan_name: PlanName
    billing_type: BillingType
    user_count: int = Field(default=1, gt=0)
    simulate_payment_success: bool = True
    custom_config: Optional[CustomPlanConfig] = None

    @model_validator(mode="after")
    def validate_custom_payload(self):
        if self.plan_name == "custom" and self.custom_config is None:
            raise ValueError("custom_config is required when plan_name is 'custom'")
        return self


class ConsumeRequest(BaseModel):
    organization_id: Optional[UUID] = None
    amount: int = Field(default=1, gt=0)
    details: Optional[dict[str, Any]] = None


class CreditMetricResponse(BaseModel):
    total: Optional[int] = None
    used: int
    remaining: Optional[int] = None
    unlimited: bool = False


class WalletResponse(BaseModel):
    organization_id: UUID
    subscription_id: int
    plan_name: str
    billing_type: str
    price_per_user: Optional[float] = None
    total_price: Optional[float] = None
    last_reset_date: datetime
    interview: CreditMetricResponse
    resume: CreditMetricResponse
    job_posting: CreditMetricResponse
    user_seat: CreditMetricResponse
    created_at: datetime
    updated_at: Optional[datetime] = None


class SubscriptionResponse(BaseModel):
    id: int
    organization_id: Optional[UUID] = Field(default=None, alias="agency_id")
    user_id: UUID
    plan_id: Optional[UUID] = None
    plan_name: str
    billing_type: str
    status: Optional[str] = None
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

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class UsageLogResponse(BaseModel):
    id: int
    organization_id: UUID
    feature_name: str
    action: str
    amount: int
    before_used: Optional[int] = None
    after_used: Optional[int] = None
    before_remaining: Optional[int] = None
    after_remaining: Optional[int] = None
    details: Optional[dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True
