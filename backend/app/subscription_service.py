from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.billing_schemas import SubscribeRequest
from app.models import Subscription, User, UserRole
from app.services.billing_service import (
    FEATURE_INTERVIEW,
    FEATURE_JOB_POST,
    FEATURE_RESUME,
    FEATURE_USER_SEAT,
    PLAN_CATALOG,
    consume_interview_credit,
    consume_job_posting,
    consume_resume_scan,
    consume_user_seat,
    get_active_subscription_for_user,
    subscribe_organization,
    utcnow,
    validate_feature_access,
)


PLAN_CONFIG = PLAN_CATALOG
PLAN_RANK = {"starter": 1, "growth": 2, "custom": 3}
PLAN_FEATURES = {FEATURE_INTERVIEW, FEATURE_JOB_POST, FEATURE_RESUME, FEATURE_USER_SEAT}
PLAN_FEATURE_ALIASES = {
    "interview": FEATURE_INTERVIEW,
    "job_post": FEATURE_JOB_POST,
    "resume_score": FEATURE_RESUME,
    "user_add": FEATURE_USER_SEAT,
}


@dataclass(frozen=True)
class PlanResolution:
    owner_user: User
    agency_id: Optional[UUID]
    active_user_count: int


def _normalize_feature(feature: str) -> str:
    return PLAN_FEATURE_ALIASES.get((feature or "").strip().lower(), (feature or "").strip().lower())


def resolve_plan_scope(db: Session, user: User) -> PlanResolution:
    if user.role == UserRole.SUPER_ADMIN and not user.agency_id:
        return PlanResolution(owner_user=user, agency_id=None, active_user_count=1 if user.is_active else 0)

    if user.agency_id:
        owner_user = (
            db.query(User)
            .filter(
                User.agency_id == user.agency_id,
                User.role == UserRole.ADMIN,
                User.is_active == True,
            )
            .order_by(User.created_at.asc(), User.id.asc())
            .first()
        ) or (
            db.query(User)
            .filter(User.agency_id == user.agency_id)
            .order_by(User.created_at.asc(), User.id.asc())
            .first()
        )
        active_user_count = (
            db.query(User)
            .filter(User.agency_id == user.agency_id, User.is_active == True)
            .count()
        )
        return PlanResolution(owner_user=owner_user or user, agency_id=user.agency_id, active_user_count=active_user_count)

    return PlanResolution(owner_user=user, agency_id=None, active_user_count=1 if user.is_active else 0)


def apply_usage_resets(subscription: Subscription, now: Optional[datetime] = None) -> Subscription:
    return subscription


def get_plan_details(plan_name: str, billing_type: str):
    return PLAN_CATALOG[(plan_name or "").strip().lower()][(billing_type or "").strip().lower()]


def get_active_subscription(db: Session, user_id: User | UUID) -> Subscription:
    if isinstance(user_id, User):
        return get_active_subscription_for_user(db, user_id)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return get_active_subscription_for_user(db, user)


def ensure_subscription_owner_access(actor: User, target_user: User) -> None:
    if actor.role == UserRole.SUPER_ADMIN:
        return
    if actor.agency_id and actor.agency_id == target_user.agency_id:
        return
    if actor.id == target_user.id:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to manage this subscription")


def is_upgrade(previous_plan: Optional[str], next_plan: str) -> bool:
    order = {"starter": 1, "growth": 2, "custom": 3}
    return order.get((next_plan or "").lower(), 0) > order.get((previous_plan or "").lower(), 0)


def select_plan(
    db: Session,
    actor_user: User,
    user_id: UUID,
    plan_name: str,
    billing_type: str,
    user_count: int,
) -> Subscription:
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    ensure_subscription_owner_access(actor_user, target_user)
    payload = SubscribeRequest(
        organization_id=target_user.agency_id,
        plan_name=plan_name,
        billing_type=billing_type,
        user_count=user_count,
        simulate_payment_success=True,
    )
    return subscribe_organization(db, actor_user, payload)


def check_plan_limit(subscription: Optional[Subscription], feature: str) -> Subscription:
    if subscription is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active subscription")
    return subscription


def get_validated_subscription(db: Session, user_id: User | UUID, feature: str) -> Subscription:
    subject_user = user_id if isinstance(user_id, User) else db.query(User).filter(User.id == user_id).first()
    if not subject_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return validate_feature_access(db, subject_user, _normalize_feature(feature))


def increment_plan_usage(
    db: Session,
    user_id: User | UUID,
    feature: str,
    amount: int = 1,
    *,
    subscription: Optional[Subscription] = None,
) -> Subscription:
    subject_user = user_id if isinstance(user_id, User) else db.query(User).filter(User.id == user_id).first()
    if not subject_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    normalized_feature = _normalize_feature(feature)
    if normalized_feature == FEATURE_INTERVIEW:
        result = consume_interview_credit(db, subject_user, amount=amount)
    elif normalized_feature == FEATURE_JOB_POST:
        result = consume_job_posting(db, subject_user, amount=amount)
    elif normalized_feature == FEATURE_RESUME:
        result = consume_resume_scan(db, subject_user, amount=amount)
    elif normalized_feature == FEATURE_USER_SEAT:
        result = consume_user_seat(db, subject_user, amount=amount)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported plan feature")

    return result
