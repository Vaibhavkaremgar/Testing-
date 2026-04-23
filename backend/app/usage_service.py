from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models import JobDescription, Plan, PlanLimit, Subscription, UsageTracking, User
from app.subscription_service import resolve_plan_scope, utcnow


FEATURE_INTERVIEW_CREDITS = "interview_credits"
FEATURE_RESUME_SCANS = "resume_scans"
FEATURE_ACTIVE_JOBS = "active_jobs"
FEATURE_USER_SEATS = "user_seats"

SUPPORTED_USAGE_FEATURES = (
    FEATURE_INTERVIEW_CREDITS,
    FEATURE_RESUME_SCANS,
    FEATURE_ACTIVE_JOBS,
    FEATURE_USER_SEATS,
)


@dataclass(frozen=True)
class UsageMetric:
    total: int
    used: int
    remaining: int


def get_active_subscription_for_usage(db: Session, current_user: User) -> Subscription:
    scope = resolve_plan_scope(db, current_user)
    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == scope.owner_user.id,
            Subscription.expires_at > utcnow(),
            or_(Subscription.status.is_(None), func.lower(Subscription.status) == "active"),
        )
        .order_by(Subscription.created_at.desc(), Subscription.id.desc())
        .first()
    )

    if not subscription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active subscription found")

    return subscription


def get_plan_for_subscription(db: Session, subscription: Subscription) -> Plan | None:
    if subscription.plan_id:
        return db.query(Plan).filter(Plan.id == subscription.plan_id).first()

    normalized_plan_name = (subscription.plan_name or "").strip().lower()
    normalized_duration = (subscription.billing_type or "").strip().lower()
    if not normalized_plan_name:
        return None

    return (
        db.query(Plan)
        .filter(
            func.lower(Plan.name) == normalized_plan_name,
            func.lower(Plan.duration) == normalized_duration,
        )
        .first()
    )


def get_plan_limits(db: Session, plan_id) -> Dict[str, int]:
    rows = db.query(PlanLimit).filter(PlanLimit.plan_id == plan_id).all()
    return {row.feature_name: row.total_limit for row in rows}


def get_usage_tracking_map(db: Session, owner_user_id) -> Dict[str, int]:
    rows = db.query(UsageTracking).filter(UsageTracking.user_id == owner_user_id).all()
    return {row.feature_name: row.used_count for row in rows}


def _count_active_jobs(db: Session, current_user: User) -> int:
    scope = resolve_plan_scope(db, current_user)
    query = db.query(JobDescription).filter(JobDescription.is_active == True)
    if scope.agency_id:
        query = query.filter(JobDescription.agency_id == scope.agency_id)
    return query.count()


def _count_active_users(db: Session, current_user: User) -> int:
    scope = resolve_plan_scope(db, current_user)
    if scope.agency_id:
        return (
            db.query(User)
            .filter(User.agency_id == scope.agency_id, User.is_active == True)
            .count()
        )
    return 1 if scope.owner_user.is_active else 0


def get_fallback_usage_count(db: Session, current_user: User, subscription: Subscription, feature_name: str) -> int:
    if feature_name == FEATURE_INTERVIEW_CREDITS:
        return subscription.interview_credits_used or 0
    if feature_name == FEATURE_RESUME_SCANS:
        return subscription.resume_scoring_used or 0
    if feature_name == FEATURE_ACTIVE_JOBS:
        return subscription.used_job_posts or _count_active_jobs(db, current_user)
    if feature_name == FEATURE_USER_SEATS:
        return subscription.current_users or _count_active_users(db, current_user)
    return 0


def build_usage_summary(db: Session, current_user: User) -> Dict[str, UsageMetric]:
    subscription = get_active_subscription_for_usage(db, current_user)
    plan = get_plan_for_subscription(db, subscription)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active subscription is not linked to a plan record",
        )

    scope = resolve_plan_scope(db, current_user)
    limits_map = get_plan_limits(db, plan.id)
    usage_map = get_usage_tracking_map(db, scope.owner_user.id)

    summary: Dict[str, UsageMetric] = {}
    for feature_name in SUPPORTED_USAGE_FEATURES:
        total = max(int(limits_map.get(feature_name, 0) or 0), 0)
        used = usage_map.get(
            feature_name,
            get_fallback_usage_count(db, current_user, subscription, feature_name),
        )
        used = max(int(used or 0), 0)
        summary[feature_name] = UsageMetric(
            total=total,
            used=used,
            remaining=max(total - used, 0),
        )

    return summary


def ensure_feature_limit_available(db: Session, current_user: User, feature_name: str, amount: int = 1) -> UsageMetric:
    normalized_feature = (feature_name or "").strip().lower()
    if normalized_feature not in SUPPORTED_USAGE_FEATURES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported usage feature")
    if amount <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Usage amount must be greater than zero")

    summary = build_usage_summary(db, current_user)
    metric = summary[normalized_feature]
    if metric.remaining < amount:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "limit_reached",
                "feature": normalized_feature,
                "message": f"{normalized_feature} limit reached for the active plan",
            },
        )
    return metric


def increment_usage_tracking(db: Session, current_user: User, feature_name: str, amount: int = 1) -> UsageMetric:
    metric = ensure_feature_limit_available(db, current_user, feature_name, amount=amount)
    scope = resolve_plan_scope(db, current_user)
    usage_row = (
        db.query(UsageTracking)
        .filter(
            UsageTracking.user_id == scope.owner_user.id,
            UsageTracking.feature_name == feature_name,
        )
        .first()
    )

    if not usage_row:
        usage_row = UsageTracking(
            user_id=scope.owner_user.id,
            feature_name=feature_name,
            used_count=0,
        )
        db.add(usage_row)
        db.flush()

    usage_row.used_count += amount
    db.add(usage_row)
    db.flush()

    return UsageMetric(
        total=metric.total,
        used=usage_row.used_count,
        remaining=max(metric.total - usage_row.used_count, 0),
    )
