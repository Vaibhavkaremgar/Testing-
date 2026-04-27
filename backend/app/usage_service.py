from __future__ import annotations

from dataclasses import dataclass
from typing import Dict
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import User
from app.services.billing_service import (
    FEATURE_INTERVIEW,
    FEATURE_JOB_POST,
    FEATURE_RESUME,
    FEATURE_USER_SEAT,
    get_wallet_summary,
)


FEATURE_INTERVIEW_CREDITS = FEATURE_INTERVIEW
FEATURE_RESUME_SCANS = FEATURE_RESUME
FEATURE_ACTIVE_JOBS = FEATURE_JOB_POST
FEATURE_USER_SEATS = FEATURE_USER_SEAT

SUPPORTED_USAGE_FEATURES = (
    FEATURE_INTERVIEW_CREDITS,
    FEATURE_RESUME_SCANS,
    FEATURE_ACTIVE_JOBS,
    FEATURE_USER_SEATS,
)


@dataclass(frozen=True)
class UsageMetric:
    total: int | None
    used: int
    remaining: int | None
    unlimited: bool = False


def _coerce_metric(total, used, remaining) -> UsageMetric:
    return UsageMetric(
        total=int(total) if total is not None else None,
        used=int(used or 0),
        remaining=int(remaining) if remaining is not None else None,
        unlimited=total is None or remaining is None,
    )


def build_usage_summary(db: Session, current_user: User) -> Dict[str, UsageMetric]:
    wallet = get_wallet_summary(db, current_user)
    return {
        FEATURE_INTERVIEW_CREDITS: _coerce_metric(wallet.interview.total, wallet.interview.used, wallet.interview.remaining),
        FEATURE_RESUME_SCANS: _coerce_metric(wallet.resume.total, wallet.resume.used, wallet.resume.remaining),
        FEATURE_ACTIVE_JOBS: _coerce_metric(wallet.job_posting.total, wallet.job_posting.used, wallet.job_posting.remaining),
        FEATURE_USER_SEATS: _coerce_metric(wallet.user_seat.total, wallet.user_seat.used, wallet.user_seat.remaining),
    }


def check_limit(db: Session, feature_name: str, org_id: UUID, amount: int = 1) -> UsageMetric:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Direct organization usage checks are deprecated. Use wallet consumption endpoints.",
    )


def ensure_feature_limit_available(db: Session, current_user: User, feature_name: str, amount: int = 1) -> UsageMetric:
    if amount <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Usage amount must be greater than zero")
    summary = build_usage_summary(db, current_user)
    normalized = (feature_name or "").strip().lower()
    if normalized not in summary:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported usage feature")
    metric = summary[normalized]
    if metric.remaining is not None and metric.remaining < amount:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "limit_reached",
                "feature": normalized,
                "message": f"{normalized} limit reached for the active plan",
            },
        )
    return metric


def increment_usage_tracking(db: Session, current_user: User, feature_name: str, amount: int = 1) -> UsageMetric:
    return ensure_feature_limit_available(db, current_user, feature_name, amount=amount)
