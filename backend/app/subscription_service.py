from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models import Subscription, User, UserRole


PLAN_CONFIG: dict[str, dict[str, dict[str, Any]]] = {
    "starter": {
        "monthly": {
            "price": 66,
            "interview_credits": 10,
            "job_postings": 5,
            "user_seats": 4,
            "resume_scoring": 500,
            "resume_scoring_unlimited": False,
            "jobs_unlimited": False,
            "expires_in_days": 30,
        },
        "yearly": {
            "price": 720,
            "interview_credits": 150,
            "job_postings": 5,
            "user_seats": 4,
            "resume_scoring": 500,
            "resume_scoring_unlimited": False,
            "jobs_unlimited": False,
            "expires_in_days": 365,
        },
    },
    "growth": {
        "monthly": {
            "price": 45,
            "interview_credits": 30,
            "job_postings": 20,
            "user_seats": 11,
            "resume_scoring": None,
            "resume_scoring_unlimited": True,
            "jobs_unlimited": False,
            "expires_in_days": 30,
        },
        "yearly": {
            "price": 499,
            "interview_credits": 360,
            "job_postings": 20,
            "user_seats": 11,
            "resume_scoring": None,
            "resume_scoring_unlimited": True,
            "jobs_unlimited": False,
            "expires_in_days": 365,
        },
    },
    "enterprise": {
        "monthly": {
            "price": None,
            "interview_credits": 500,
            "job_postings": None,
            "user_seats": None,
            "resume_scoring": None,
            "resume_scoring_unlimited": True,
            "jobs_unlimited": True,
            "expires_in_days": 30,
        },
        "yearly": {
            "price": None,
            "interview_credits": 6000,
            "job_postings": None,
            "user_seats": None,
            "resume_scoring": None,
            "resume_scoring_unlimited": True,
            "jobs_unlimited": True,
            "expires_in_days": 365,
        },
    },
}

PLAN_RANK = {"starter": 1, "growth": 2, "enterprise": 3}
PLAN_FEATURES = {"interview", "job_post", "user_add", "resume_score"}
MONTHLY_RESET_INTERVAL = timedelta(days=30)
PLAN_LIMIT_ERRORS = {
    "interview": {
        "error": "limit_reached",
        "message": "Interview credits exhausted. To continue services, please recharge your plan.",
        "feature": "interview",
    },
    "job_post": {
        "error": "limit_reached",
        "message": "Job posting limit reached. To continue services, please recharge your plan.",
        "feature": "job_post",
    },
    "user_add": {
        "error": "limit_reached",
        "message": "User limit reached. Please upgrade or recharge your plan.",
        "feature": "user_add",
    },
    "resume_score": {
        "error": "limit_reached",
        "message": "Resume scoring limit reached. To continue services, please recharge your plan.",
        "feature": "resume_score",
    },
}


@dataclass(frozen=True)
class PlanResolution:
    owner_user: User
    agency_id: Optional[UUID]
    active_user_count: int


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _raise_limit_reached(feature: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=PLAN_LIMIT_ERRORS[feature],
    )


def get_plan_details(plan_name: str, billing_type: str) -> dict[str, Any]:
    normalized_plan = (plan_name or "").strip().lower()
    normalized_billing = (billing_type or "").strip().lower()
    plan = PLAN_CONFIG.get(normalized_plan)
    if not plan or normalized_billing not in plan:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid plan or billing type")
    return plan[normalized_billing]


def _get_user_by_id(db: Session, user_id: UUID) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _resolve_subject_user(db: Session, user_or_id: User | UUID) -> User:
    if isinstance(user_or_id, User):
        return user_or_id
    return _get_user_by_id(db, user_or_id)


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
        if not owner_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription owner not found")
        return PlanResolution(owner_user=owner_user, agency_id=user.agency_id, active_user_count=active_user_count)

    return PlanResolution(owner_user=user, agency_id=None, active_user_count=1 if user.is_active else 0)


def _get_owner_subscription_query(db: Session, owner_user_id: UUID):
    return (
        db.query(Subscription)
        .filter(Subscription.user_id == owner_user_id)
        .order_by(Subscription.created_at.desc(), Subscription.id.desc())
    )


def _get_latest_subscription(db: Session, owner_user_id: UUID) -> Optional[Subscription]:
    return _get_owner_subscription_query(db, owner_user_id).first()


def _get_latest_active_subscription(db: Session, owner_user_id: UUID) -> Optional[Subscription]:
    return (
        _get_owner_subscription_query(db, owner_user_id)
        .filter(Subscription.expires_at > utcnow())
        .first()
    )


def apply_usage_resets(subscription: Subscription, now: Optional[datetime] = None) -> Subscription:
    now = _as_utc(now) or utcnow()
    last_reset = _as_utc(subscription.last_monthly_reset_at) or _as_utc(subscription.created_at) or now

    while last_reset + MONTHLY_RESET_INTERVAL <= now:
        last_reset = last_reset + MONTHLY_RESET_INTERVAL
        subscription.used_job_posts = 0
        if subscription.billing_type == "monthly":
            subscription.interview_credits_used = 0
        if not subscription.is_unlimited_resume_scoring:
            subscription.resume_scoring_used = 0

    subscription.last_monthly_reset_at = last_reset
    return subscription


def _sync_current_users(db: Session, subscription: Subscription, scope: PlanResolution) -> Subscription:
    subscription.current_users = scope.active_user_count
    db.add(subscription)
    db.flush()
    return subscription


def get_active_subscription(db: Session, user_id: User | UUID) -> Subscription:
    subject_user = _resolve_subject_user(db, user_id)
    scope = resolve_plan_scope(db, subject_user)
    subscription = _get_latest_active_subscription(db, scope.owner_user.id)
    if not subscription:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No active subscription")

    apply_usage_resets(subscription)
    _sync_current_users(db, subscription, scope)

    if _as_utc(subscription.expires_at) <= utcnow():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Subscription expired")

    return subscription


def ensure_subscription_owner_access(actor: User, target_user: User) -> None:
    if actor.role == UserRole.SUPER_ADMIN:
        return
    if actor.agency_id and actor.agency_id == target_user.agency_id:
        return
    if actor.id == target_user.id:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to manage this subscription")


def is_upgrade(previous_plan: Optional[str], next_plan: str) -> bool:
    if not previous_plan:
        return False
    return PLAN_RANK.get(next_plan, 0) > PLAN_RANK.get(previous_plan, 0)


def select_plan(
    db: Session,
    actor_user: User,
    user_id: UUID,
    plan_name: str,
    billing_type: str,
    user_count: int,
) -> Subscription:
    if user_count <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_count must be greater than 0")

    target_user = _get_user_by_id(db, user_id)
    ensure_subscription_owner_access(actor_user, target_user)

    normalized_plan = (plan_name or "").strip().lower()
    normalized_billing = (billing_type or "").strip().lower()
    plan_details = get_plan_details(normalized_plan, normalized_billing)
    scope = resolve_plan_scope(db, target_user)
    existing = _get_latest_subscription(db, scope.owner_user.id)

    price_per_user = plan_details["price"]
    total_price = (price_per_user * user_count) if price_per_user is not None else None
    carry_forward_interviews = 0
    now = utcnow()

    if existing:
        apply_usage_resets(existing, now=now)
        if _as_utc(existing.expires_at) > now and is_upgrade(existing.plan_name, normalized_plan):
            carry_forward_interviews = max(
                (existing.interview_credits_total or 0) - (existing.interview_credits_used or 0),
                0,
            )

    subscription = Subscription(
        user_id=scope.owner_user.id,
        plan_name=normalized_plan,
        billing_type=normalized_billing,
        price_per_user=price_per_user,
        total_price=total_price,
        interview_credits_total=(plan_details["interview_credits"] or 0) + carry_forward_interviews,
        interview_credits_used=0,
        max_job_posts=None if plan_details["jobs_unlimited"] else plan_details["job_postings"],
        used_job_posts=0,
        max_users=plan_details["user_seats"],
        current_users=scope.active_user_count,
        resume_scoring_limit=None if plan_details["resume_scoring_unlimited"] else plan_details["resume_scoring"],
        resume_scoring_used=0,
        is_unlimited_resume_scoring=plan_details["resume_scoring_unlimited"],
        is_unlimited_jobs=plan_details["jobs_unlimited"],
        expires_at=now + timedelta(days=plan_details["expires_in_days"]),
        cycle_anchor_at=now,
        last_monthly_reset_at=now,
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription


def check_plan_limit(subscription: Optional[Subscription], feature: str) -> Subscription:
    normalized_feature = (feature or "").strip().lower()
    if normalized_feature not in PLAN_FEATURES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported plan feature")

    if subscription is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No active subscription")

    if _as_utc(subscription.expires_at) <= utcnow():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Subscription expired")

    if normalized_feature == "interview":
        if (subscription.interview_credits_used or 0) >= (subscription.interview_credits_total or 0):
            _raise_limit_reached("interview")
    elif normalized_feature == "job_post":
        if not subscription.is_unlimited_jobs and (subscription.used_job_posts or 0) >= (subscription.max_job_posts or 0):
            _raise_limit_reached("job_post")
    elif normalized_feature == "user_add":
        if subscription.max_users is not None and (subscription.current_users or 0) >= subscription.max_users:
            _raise_limit_reached("user_add")
    elif normalized_feature == "resume_score":
        if (
            not subscription.is_unlimited_resume_scoring
            and (subscription.resume_scoring_used or 0) >= (subscription.resume_scoring_limit or 0)
        ):
            _raise_limit_reached("resume_score")

    return subscription


def get_validated_subscription(db: Session, user_id: User | UUID, feature: str) -> Subscription:
    subject_user = _resolve_subject_user(db, user_id)
    subscription = get_active_subscription(db, subject_user)
    scope = resolve_plan_scope(db, subject_user)
    subscription.current_users = scope.active_user_count
    return check_plan_limit(subscription, feature)


def increment_plan_usage(
    db: Session,
    user_id: User | UUID,
    feature: str,
    amount: int = 1,
    *,
    subscription: Optional[Subscription] = None,
) -> Subscription:
    if amount <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Usage increment must be positive")

    normalized_feature = (feature or "").strip().lower()
    target_subscription = subscription or get_validated_subscription(db, user_id, normalized_feature)

    if normalized_feature == "interview":
        result = db.execute(
            update(Subscription)
            .where(
                Subscription.id == target_subscription.id,
                Subscription.interview_credits_used + amount <= Subscription.interview_credits_total,
            )
            .values(interview_credits_used=Subscription.interview_credits_used + amount)
        )
        if result.rowcount == 0:
            _raise_limit_reached("interview")
    elif normalized_feature == "job_post":
        result = db.execute(
            update(Subscription)
            .where(
                Subscription.id == target_subscription.id,
                Subscription.is_unlimited_jobs == False,
                Subscription.used_job_posts + amount <= Subscription.max_job_posts,
            )
            .values(used_job_posts=Subscription.used_job_posts + amount)
        )
        if target_subscription.is_unlimited_jobs:
            db.refresh(target_subscription)
            return target_subscription
        if result.rowcount == 0:
            _raise_limit_reached("job_post")
    elif normalized_feature == "user_add":
        result = db.execute(
            update(Subscription)
            .where(
                Subscription.id == target_subscription.id,
                Subscription.max_users.is_not(None),
                Subscription.current_users + amount <= Subscription.max_users,
            )
            .values(current_users=Subscription.current_users + amount)
        )
        if target_subscription.max_users is None:
            db.refresh(target_subscription)
            return target_subscription
        if result.rowcount == 0:
            _raise_limit_reached("user_add")
    elif normalized_feature == "resume_score":
        if target_subscription.is_unlimited_resume_scoring:
            db.refresh(target_subscription)
            return target_subscription
        result = db.execute(
            update(Subscription)
            .where(
                Subscription.id == target_subscription.id,
                Subscription.resume_scoring_used + amount <= Subscription.resume_scoring_limit,
            )
            .values(resume_scoring_used=Subscription.resume_scoring_used + amount)
        )
        if result.rowcount == 0:
            _raise_limit_reached("resume_score")

    db.flush()
    db.refresh(target_subscription)
    return target_subscription
