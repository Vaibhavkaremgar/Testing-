from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.billing_schemas import CustomPlanConfig, SubscribeRequest, WalletResponse
from app.models import Agency, Plan, PlanLimit, Subscription, TransactionType, UsageLog, User, UserRole, Wallet, WalletTransaction


FEATURE_INTERVIEW = "interview"
FEATURE_RESUME = "resume_score"
FEATURE_JOB_POST = "job_post"
FEATURE_USER_SEAT = "user_add"
MONTHLY_RESET_INTERVAL = timedelta(days=30)

FEATURE_ALIASES = {
    "interview": FEATURE_INTERVIEW,
    "interview_credit": FEATURE_INTERVIEW,
    "resume": FEATURE_RESUME,
    "resume_scan": FEATURE_RESUME,
    "resume_score": FEATURE_RESUME,
    "job": FEATURE_JOB_POST,
    "job_post": FEATURE_JOB_POST,
    "job_posting": FEATURE_JOB_POST,
    "user": FEATURE_USER_SEAT,
    "user_add": FEATURE_USER_SEAT,
    "user_seat": FEATURE_USER_SEAT,
}

PLAN_CATALOG: dict[str, dict[str, dict[str, Any]]] = {
    "starter": {
        "monthly": {
            "price_per_user": 66,
            "interview_credits": 10,
            "resume_scans": 500,
            "job_postings": 5,
            "user_seats": 4,
        },
        "yearly": {
            "price_per_user": 720,
            "interview_credits": 150,
            "resume_scans": 500,
            "job_postings": 5,
            "user_seats": 4,
        },
    },
    "growth": {
        "monthly": {
            "price_per_user": 45,
            "interview_credits": 30,
            "resume_scans": None,
            "job_postings": 20,
            "user_seats": 11,
            "unlimited_resume_scans": True,
        },
        "yearly": {
            "price_per_user": 499,
            "interview_credits": 360,
            "resume_scans": None,
            "job_postings": 20,
            "user_seats": 11,
            "unlimited_resume_scans": True,
        },
    },
    "custom": {
        "monthly": {
            "price_per_user": None,
            "interview_credits": None,
            "resume_scans": None,
            "job_postings": None,
            "user_seats": None,
        },
        "yearly": {
            "price_per_user": None,
            "interview_credits": None,
            "resume_scans": None,
            "job_postings": None,
            "user_seats": None,
        },
    },
}


@dataclass(frozen=True)
class BillingScope:
    agency: Agency
    owner_user: User
    active_user_count: int


@dataclass(frozen=True)
class PlanDefinition:
    name: str
    billing_type: str
    price_per_user: Optional[float]
    interview_total: Optional[int]
    resume_total: Optional[int]
    job_post_total: Optional[int]
    user_seat_total: Optional[int]
    interview_unlimited: bool
    resume_unlimited: bool
    job_post_unlimited: bool
    user_seat_unlimited: bool
    expires_in_days: int


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _normalize_feature_name(feature_name: str) -> str:
    normalized = (feature_name or "").strip().lower()
    feature = FEATURE_ALIASES.get(normalized)
    if not feature:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported usage feature")
    return feature


def _feature_error(feature_name: str) -> dict[str, str]:
    messages = {
        FEATURE_INTERVIEW: "Interview credits exhausted for the active subscription.",
        FEATURE_RESUME: "Resume scan limit reached for the active subscription.",
        FEATURE_JOB_POST: "Job posting limit reached for the active subscription.",
        FEATURE_USER_SEAT: "User seat limit reached for the active subscription.",
    }
    return {
        "error": "limit_reached",
        "feature": feature_name,
        "message": messages[feature_name],
    }


def _raise_limit_reached(feature_name: str) -> None:
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_feature_error(feature_name))


def _resolve_scope(db: Session, actor_user: User, organization_id: Optional[UUID] = None) -> BillingScope:
    target_agency_id = organization_id

    if actor_user.role == UserRole.SUPER_ADMIN:
        if target_agency_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="organization_id is required for super admin actions")
    else:
        if actor_user.agency_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current user is not assigned to an organization")
        if target_agency_id and target_agency_id != actor_user.agency_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Outside your organization scope")
        target_agency_id = actor_user.agency_id

    agency = db.query(Agency).filter(Agency.id == target_agency_id).first()
    if not agency:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    owner_user = (
        db.query(User)
        .filter(
            User.agency_id == agency.id,
            User.role == UserRole.ADMIN,
            User.is_active == True,
        )
        .order_by(User.created_at.asc(), User.id.asc())
        .first()
    ) or (
        db.query(User)
        .filter(User.agency_id == agency.id)
        .order_by(User.created_at.asc(), User.id.asc())
        .first()
    )
    if not owner_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization owner not found")

    active_user_count = (
        db.query(func.count(User.id))
        .filter(User.agency_id == agency.id, User.is_active == True)
        .scalar()
        or 0
    )
    return BillingScope(agency=agency, owner_user=owner_user, active_user_count=active_user_count)


def _get_or_create_plan(
    db: Session,
    *,
    plan_name: str,
    billing_type: str,
    price_per_user: Optional[float],
    definition: PlanDefinition,
) -> Plan:
    plan = (
        db.query(Plan)
        .filter(
            func.lower(Plan.name) == plan_name.lower(),
            func.lower(Plan.duration) == billing_type.lower(),
        )
        .first()
    )
    if not plan:
        plan = Plan(name=plan_name, duration=billing_type)
        db.add(plan)
        db.flush()

    plan.price = price_per_user
    db.add(plan)
    db.flush()

    limits = {
        FEATURE_INTERVIEW: definition.interview_total,
        FEATURE_RESUME: definition.resume_total,
        FEATURE_JOB_POST: definition.job_post_total,
        FEATURE_USER_SEAT: definition.user_seat_total,
    }
    for feature_name, total_limit in limits.items():
        row = (
            db.query(PlanLimit)
            .filter(PlanLimit.plan_id == plan.id, PlanLimit.feature_name == feature_name)
            .first()
        )
        if row is None:
            row = PlanLimit(plan_id=plan.id, feature_name=feature_name, total_limit=int(total_limit or 0))
            db.add(row)
        else:
            row.total_limit = int(total_limit or 0)
            db.add(row)

    db.flush()
    return plan


def ensure_plan_catalog(db: Session) -> None:
    for plan_name, durations in PLAN_CATALOG.items():
        if plan_name == "custom":
            continue
        for billing_type, config in durations.items():
            definition = _build_plan_definition(plan_name, billing_type, None)
            _get_or_create_plan(
                db,
                plan_name=plan_name,
                billing_type=billing_type,
                price_per_user=config.get("price_per_user"),
                definition=definition,
            )
    db.commit()


def _build_plan_definition(plan_name: str, billing_type: str, custom_config: Optional[CustomPlanConfig]) -> PlanDefinition:
    normalized_plan = (plan_name or "").strip().lower()
    normalized_billing = (billing_type or "").strip().lower()
    if normalized_plan not in PLAN_CATALOG or normalized_billing not in PLAN_CATALOG[normalized_plan]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid plan_name or billing_type")

    config = dict(PLAN_CATALOG[normalized_plan][normalized_billing])
    if normalized_plan == "custom":
        if custom_config is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="custom_config is required for custom plans")
        config.update(custom_config.model_dump())

    return PlanDefinition(
        name=normalized_plan,
        billing_type=normalized_billing,
        price_per_user=config.get("price_per_user"),
        interview_total=None if config.get("unlimited_interviews", False) else config.get("interview_credits"),
        resume_total=None if config.get("unlimited_resume_scans", False) else config.get("resume_scans"),
        job_post_total=None if config.get("unlimited_job_postings", False) else config.get("job_postings"),
        user_seat_total=None if config.get("unlimited_user_seats", False) else config.get("user_seats"),
        interview_unlimited=bool(config.get("unlimited_interviews", False)),
        resume_unlimited=bool(config.get("unlimited_resume_scans", False)),
        job_post_unlimited=bool(config.get("unlimited_job_postings", False)),
        user_seat_unlimited=bool(config.get("unlimited_user_seats", False)),
        expires_in_days=365 if normalized_billing == "yearly" else 30,
    )


def _get_active_subscription(db: Session, scope: BillingScope) -> Subscription:
    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.agency_id == scope.agency.id,
            Subscription.expires_at > utcnow(),
            func.coalesce(func.lower(Subscription.status), "active") == "active",
        )
        .order_by(Subscription.created_at.desc(), Subscription.id.desc())
        .first()
    )
    if not subscription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active subscription found")
    return subscription


def _get_wallet(db: Session, scope: BillingScope) -> Wallet:
    wallet = db.query(Wallet).filter(Wallet.agency_id == scope.agency.id).first()
    if not wallet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not initialized for organization")
    return wallet


def _safe_remaining(total: Optional[int], used: int, unlimited: bool) -> Optional[int]:
    if unlimited or total is None:
        return None
    return max(int(total) - int(used), 0)


def _log_usage(
    db: Session,
    *,
    wallet: Wallet,
    subscription: Subscription,
    actor_user: Optional[User],
    feature_name: str,
    action: str,
    amount: int,
    before_used: Optional[int],
    after_used: Optional[int],
    before_remaining: Optional[int],
    after_remaining: Optional[int],
    details: Optional[dict[str, Any]] = None,
) -> None:
    log = UsageLog(
        agency_id=wallet.agency_id,
        subscription_id=subscription.id,
        wallet_id=wallet.id,
        user_id=actor_user.id if actor_user else None,
        feature_name=feature_name,
        action=action,
        amount=amount,
        before_used=before_used,
        after_used=after_used,
        before_remaining=before_remaining,
        after_remaining=after_remaining,
        details=details,
    )
    db.add(log)


def _sync_user_seats(wallet: Wallet, subscription: Subscription, scope: BillingScope) -> Wallet:
    current_users = max(int(scope.active_user_count or 0), 0)
    wallet.user_seat_used = current_users
    subscription.current_users = current_users
    wallet.user_seat_remaining = _safe_remaining(wallet.user_seat_total, wallet.user_seat_used, wallet.is_user_seat_unlimited)
    return wallet


def _get_interview_cycle_start(subscription: Subscription, wallet: Wallet) -> datetime:
    if subscription.billing_type == "monthly":
        return (
            _as_utc(subscription.last_monthly_reset_at)
            or _as_utc(wallet.last_reset_date)
            or _as_utc(subscription.cycle_anchor_at)
            or _as_utc(subscription.created_at)
            or utcnow()
        )

    return (
        _as_utc(subscription.cycle_anchor_at)
        or _as_utc(subscription.created_at)
        or utcnow()
    )


def _reconcile_interview_usage_from_transactions(
    db: Session,
    wallet: Wallet,
    subscription: Subscription,
    scope: BillingScope,
) -> Wallet:
    cycle_start = _get_interview_cycle_start(subscription, wallet)
    billed_interview_total = (
        db.query(func.coalesce(func.sum(WalletTransaction.amount), 0))
        .filter(
            WalletTransaction.user_id == scope.owner_user.id,
            WalletTransaction.agency_id == scope.agency.id,
            WalletTransaction.transaction_type == TransactionType.DEBIT,
            WalletTransaction.description.like("Interview completed - Interview ID %"),
            WalletTransaction.created_at >= cycle_start,
        )
        .scalar()
    ) or 0

    billed_interview_total = int(billed_interview_total)
    if wallet.interview_used != billed_interview_total or subscription.interview_credits_used != billed_interview_total:
        wallet.interview_used = billed_interview_total
        subscription.interview_credits_used = billed_interview_total
        wallet.interview_remaining = _safe_remaining(wallet.interview_total, wallet.interview_used, wallet.is_interview_unlimited)
        db.add(wallet)
        db.add(subscription)
        db.flush()

    return wallet


def reset_monthly_credits(db: Session, wallet: Wallet, subscription: Subscription, scope: BillingScope) -> Wallet:
    now = utcnow()
    last_reset = _as_utc(wallet.last_reset_date) or _as_utc(subscription.last_monthly_reset_at) or _as_utc(subscription.created_at) or now

    changed = False
    while last_reset + MONTHLY_RESET_INTERVAL <= now:
        last_reset = last_reset + MONTHLY_RESET_INTERVAL
        changed = True

    if changed:
        if subscription.billing_type == "monthly":
            wallet.interview_used = 0
            subscription.interview_credits_used = 0
        wallet.resume_used = 0
        subscription.resume_scoring_used = 0
        wallet.job_post_used = 0
        subscription.used_job_posts = 0
        wallet.last_reset_date = last_reset
        subscription.last_monthly_reset_at = last_reset

        _log_usage(
            db,
            wallet=wallet,
            subscription=subscription,
            actor_user=None,
            feature_name="monthly_reset",
            action="reset",
            amount=1,
            before_used=None,
            after_used=None,
            before_remaining=None,
            after_remaining=None,
            details={"billing_type": subscription.billing_type, "reset_at": last_reset.isoformat()},
        )

    wallet.interview_remaining = _safe_remaining(wallet.interview_total, wallet.interview_used, wallet.is_interview_unlimited)
    wallet.resume_remaining = _safe_remaining(wallet.resume_total, wallet.resume_used, wallet.is_resume_unlimited)
    wallet.job_post_remaining = _safe_remaining(wallet.job_post_total, wallet.job_post_used, wallet.is_job_post_unlimited)
    _sync_user_seats(wallet, subscription, scope)
    _reconcile_interview_usage_from_transactions(db, wallet, subscription, scope)
    db.add(wallet)
    db.add(subscription)
    db.flush()
    return wallet


def _build_wallet_response(wallet: Wallet, subscription: Subscription) -> WalletResponse:
    return WalletResponse(
        organization_id=wallet.agency_id,
        subscription_id=subscription.id,
        plan_name=subscription.plan_name,
        billing_type=subscription.billing_type,
        price_per_user=subscription.price_per_user,
        total_price=subscription.total_price,
        last_reset_date=wallet.last_reset_date,
        interview={
            "total": wallet.interview_total,
            "used": wallet.interview_used,
            "remaining": wallet.interview_remaining,
            "unlimited": wallet.is_interview_unlimited,
        },
        resume={
            "total": wallet.resume_total,
            "used": wallet.resume_used,
            "remaining": wallet.resume_remaining,
            "unlimited": wallet.is_resume_unlimited,
        },
        job_posting={
            "total": wallet.job_post_total,
            "used": wallet.job_post_used,
            "remaining": wallet.job_post_remaining,
            "unlimited": wallet.is_job_post_unlimited,
        },
        user_seat={
            "total": wallet.user_seat_total,
            "used": wallet.user_seat_used,
            "remaining": wallet.user_seat_remaining,
            "unlimited": wallet.is_user_seat_unlimited,
        },
        created_at=wallet.created_at,
        updated_at=wallet.updated_at,
    )


def subscribe_organization(db: Session, actor_user: User, payload: SubscribeRequest) -> Subscription:
    if actor_user.role not in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can subscribe an organization")
    if not payload.simulate_payment_success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment simulation failed")

    definition = _build_plan_definition(payload.plan_name, payload.billing_type, payload.custom_config)
    scope = _resolve_scope(db, actor_user, payload.organization_id)
    plan = _get_or_create_plan(
        db,
        plan_name=definition.name,
        billing_type=definition.billing_type,
        price_per_user=definition.price_per_user,
        definition=definition,
    )

    (
        db.query(Subscription)
        .filter(
            Subscription.agency_id == scope.agency.id,
            func.coalesce(func.lower(Subscription.status), "active") == "active",
        )
        .update({"status": "expired"}, synchronize_session=False)
    )

    now = utcnow()
    subscription = Subscription(
        agency_id=scope.agency.id,
        user_id=scope.owner_user.id,
        plan_id=plan.id,
        status="active",
        plan_name=definition.name,
        billing_type=definition.billing_type,
        price_per_user=definition.price_per_user,
        total_price=(definition.price_per_user * payload.user_count) if definition.price_per_user is not None else None,
        interview_credits_total=definition.interview_total,
        interview_credits_used=0,
        max_job_posts=definition.job_post_total,
        used_job_posts=0,
        max_users=definition.user_seat_total,
        current_users=scope.active_user_count,
        resume_scoring_limit=definition.resume_total,
        resume_scoring_used=0,
        is_unlimited_resume_scoring=definition.resume_unlimited,
        is_unlimited_jobs=definition.job_post_unlimited,
        expires_at=now + timedelta(days=definition.expires_in_days),
        cycle_anchor_at=now,
        last_monthly_reset_at=now,
    )
    db.add(subscription)
    db.flush()

    wallet = db.query(Wallet).filter(Wallet.agency_id == scope.agency.id).first()
    if wallet is None:
        wallet = Wallet(
            agency_id=scope.agency.id,
            subscription_id=subscription.id,
        )
        db.add(wallet)

    wallet.subscription_id = subscription.id
    wallet.interview_total = definition.interview_total
    wallet.interview_used = 0
    wallet.is_interview_unlimited = definition.interview_unlimited
    wallet.interview_remaining = _safe_remaining(definition.interview_total, 0, definition.interview_unlimited)

    wallet.resume_total = definition.resume_total
    wallet.resume_used = 0
    wallet.is_resume_unlimited = definition.resume_unlimited
    wallet.resume_remaining = _safe_remaining(definition.resume_total, 0, definition.resume_unlimited)

    wallet.job_post_total = definition.job_post_total
    wallet.job_post_used = 0
    wallet.is_job_post_unlimited = definition.job_post_unlimited
    wallet.job_post_remaining = _safe_remaining(definition.job_post_total, 0, definition.job_post_unlimited)

    wallet.user_seat_total = definition.user_seat_total
    wallet.is_user_seat_unlimited = definition.user_seat_unlimited
    wallet.last_reset_date = now
    _sync_user_seats(wallet, subscription, scope)
    db.add(wallet)
    db.flush()

    _log_usage(
        db,
        wallet=wallet,
        subscription=subscription,
        actor_user=actor_user,
        feature_name="subscription",
        action="subscribe",
        amount=payload.user_count,
        before_used=None,
        after_used=None,
        before_remaining=None,
        after_remaining=None,
        details={
            "plan_name": payload.plan_name,
            "billing_type": payload.billing_type,
            "simulate_payment_success": payload.simulate_payment_success,
        },
    )

    db.commit()
    db.refresh(subscription)
    return subscription


def get_active_subscription_for_user(db: Session, actor_user: User, organization_id: Optional[UUID] = None) -> Subscription:
    scope = _resolve_scope(db, actor_user, organization_id)
    subscription = _get_active_subscription(db, scope)
    wallet = _get_wallet(db, scope)
    reset_monthly_credits(db, wallet, subscription, scope)
    db.commit()
    db.refresh(subscription)
    return subscription


def get_wallet_summary(db: Session, actor_user: User, organization_id: Optional[UUID] = None) -> WalletResponse:
    scope = _resolve_scope(db, actor_user, organization_id)
    subscription = _get_active_subscription(db, scope)
    wallet = _get_wallet(db, scope)
    reset_monthly_credits(db, wallet, subscription, scope)
    db.commit()
    db.refresh(wallet)
    db.refresh(subscription)
    return _build_wallet_response(wallet, subscription)


def _consume_feature(
    db: Session,
    actor_user: User,
    feature_name: str,
    *,
    amount: int = 1,
    organization_id: Optional[UUID] = None,
    details: Optional[dict[str, Any]] = None,
) -> Subscription:
    if amount <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="amount must be greater than zero")

    feature = _normalize_feature_name(feature_name)
    scope = _resolve_scope(db, actor_user, organization_id)
    subscription = _get_active_subscription(db, scope)
    wallet = _get_wallet(db, scope)
    reset_monthly_credits(db, wallet, subscription, scope)

    if feature == FEATURE_INTERVIEW:
        before_used = wallet.interview_used
        before_remaining = wallet.interview_remaining
        if not wallet.is_interview_unlimited and (wallet.interview_remaining or 0) < amount:
            _raise_limit_reached(feature)
        wallet.interview_used += amount
        subscription.interview_credits_used += amount
        wallet.interview_remaining = _safe_remaining(wallet.interview_total, wallet.interview_used, wallet.is_interview_unlimited)
        _log_usage(db, wallet=wallet, subscription=subscription, actor_user=actor_user, feature_name=feature, action="consume", amount=amount, before_used=before_used, after_used=wallet.interview_used, before_remaining=before_remaining, after_remaining=wallet.interview_remaining, details=details)
    elif feature == FEATURE_RESUME:
        before_used = wallet.resume_used
        before_remaining = wallet.resume_remaining
        if not wallet.is_resume_unlimited and (wallet.resume_remaining or 0) < amount:
            _raise_limit_reached(feature)
        wallet.resume_used += amount
        subscription.resume_scoring_used += amount
        wallet.resume_remaining = _safe_remaining(wallet.resume_total, wallet.resume_used, wallet.is_resume_unlimited)
        _log_usage(db, wallet=wallet, subscription=subscription, actor_user=actor_user, feature_name=feature, action="consume", amount=amount, before_used=before_used, after_used=wallet.resume_used, before_remaining=before_remaining, after_remaining=wallet.resume_remaining, details=details)
    elif feature == FEATURE_JOB_POST:
        before_used = wallet.job_post_used
        before_remaining = wallet.job_post_remaining
        if not wallet.is_job_post_unlimited and (wallet.job_post_remaining or 0) < amount:
            _raise_limit_reached(feature)
        wallet.job_post_used += amount
        subscription.used_job_posts += amount
        wallet.job_post_remaining = _safe_remaining(wallet.job_post_total, wallet.job_post_used, wallet.is_job_post_unlimited)
        _log_usage(db, wallet=wallet, subscription=subscription, actor_user=actor_user, feature_name=feature, action="consume", amount=amount, before_used=before_used, after_used=wallet.job_post_used, before_remaining=before_remaining, after_remaining=wallet.job_post_remaining, details=details)
    elif feature == FEATURE_USER_SEAT:
        before_used = wallet.user_seat_used
        before_remaining = wallet.user_seat_remaining
        if not wallet.is_user_seat_unlimited and (wallet.user_seat_remaining or 0) < amount:
            _raise_limit_reached(feature)
        wallet.user_seat_used += amount
        subscription.current_users += amount
        wallet.user_seat_remaining = _safe_remaining(wallet.user_seat_total, wallet.user_seat_used, wallet.is_user_seat_unlimited)
        _log_usage(db, wallet=wallet, subscription=subscription, actor_user=actor_user, feature_name=feature, action="consume", amount=amount, before_used=before_used, after_used=wallet.user_seat_used, before_remaining=before_remaining, after_remaining=wallet.user_seat_remaining, details=details)

    db.add(wallet)
    db.add(subscription)
    db.flush()
    return subscription


def consume_interview_credit(db: Session, actor_user: User, *, amount: int = 1, organization_id: Optional[UUID] = None, details: Optional[dict[str, Any]] = None) -> Subscription:
    return _consume_feature(db, actor_user, FEATURE_INTERVIEW, amount=amount, organization_id=organization_id, details=details)


def consume_resume_scan(db: Session, actor_user: User, *, amount: int = 1, organization_id: Optional[UUID] = None, details: Optional[dict[str, Any]] = None) -> Subscription:
    return _consume_feature(db, actor_user, FEATURE_RESUME, amount=amount, organization_id=organization_id, details=details)


def consume_job_posting(db: Session, actor_user: User, *, amount: int = 1, organization_id: Optional[UUID] = None, details: Optional[dict[str, Any]] = None) -> Subscription:
    return _consume_feature(db, actor_user, FEATURE_JOB_POST, amount=amount, organization_id=organization_id, details=details)


def consume_user_seat(db: Session, actor_user: User, *, amount: int = 1, organization_id: Optional[UUID] = None, details: Optional[dict[str, Any]] = None) -> Subscription:
    return _consume_feature(db, actor_user, FEATURE_USER_SEAT, amount=amount, organization_id=organization_id, details=details)


def validate_feature_access(
    db: Session,
    actor_user: User,
    feature_name: str,
    *,
    amount: int = 1,
    organization_id: Optional[UUID] = None,
) -> Subscription:
    feature = _normalize_feature_name(feature_name)
    scope = _resolve_scope(db, actor_user, organization_id)
    subscription = _get_active_subscription(db, scope)
    wallet = _get_wallet(db, scope)
    reset_monthly_credits(db, wallet, subscription, scope)

    remaining_lookup = {
        FEATURE_INTERVIEW: wallet.interview_remaining,
        FEATURE_RESUME: wallet.resume_remaining,
        FEATURE_JOB_POST: wallet.job_post_remaining,
        FEATURE_USER_SEAT: wallet.user_seat_remaining,
    }
    unlimited_lookup = {
        FEATURE_INTERVIEW: wallet.is_interview_unlimited,
        FEATURE_RESUME: wallet.is_resume_unlimited,
        FEATURE_JOB_POST: wallet.is_job_post_unlimited,
        FEATURE_USER_SEAT: wallet.is_user_seat_unlimited,
    }

    if not unlimited_lookup[feature] and (remaining_lookup[feature] or 0) < amount:
        _raise_limit_reached(feature)
    return subscription
