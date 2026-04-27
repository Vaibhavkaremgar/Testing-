from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from uuid import UUID

from app.auth import get_current_active_user
from app.billing_schemas import ConsumeRequest, SubscriptionResponse, SubscribeRequest, WalletResponse
from app.database import get_db
from app.models import User
from app.services.billing_service import (
    consume_interview_credit,
    consume_job_posting,
    consume_resume_scan,
    consume_user_seat,
    get_wallet_summary,
    subscribe_organization,
)


router = APIRouter(tags=["Billing"])


@router.get("/wallet", response_model=WalletResponse)
def get_wallet(
    organization_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return get_wallet_summary(db, current_user, organization_id)


@router.post("/subscribe", response_model=SubscriptionResponse)
def subscribe(
    payload: SubscribeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return subscribe_organization(db, current_user, payload)


@router.post("/consume/interview", response_model=SubscriptionResponse)
def consume_interview(
    payload: ConsumeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    subscription = consume_interview_credit(
        db,
        current_user,
        amount=payload.amount,
        organization_id=payload.organization_id,
        details=payload.details,
    )
    db.commit()
    db.refresh(subscription)
    return subscription


@router.post("/consume/resume", response_model=SubscriptionResponse)
def consume_resume(
    payload: ConsumeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    subscription = consume_resume_scan(
        db,
        current_user,
        amount=payload.amount,
        organization_id=payload.organization_id,
        details=payload.details,
    )
    db.commit()
    db.refresh(subscription)
    return subscription


@router.post("/consume/job", response_model=SubscriptionResponse)
def consume_job(
    payload: ConsumeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    subscription = consume_job_posting(
        db,
        current_user,
        amount=payload.amount,
        organization_id=payload.organization_id,
        details=payload.details,
    )
    db.commit()
    db.refresh(subscription)
    return subscription


@router.post("/consume/user-seat", response_model=SubscriptionResponse)
def consume_user_seat_route(
    payload: ConsumeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    subscription = consume_user_seat(
        db,
        current_user,
        amount=payload.amount,
        organization_id=payload.organization_id,
        details=payload.details,
    )
    db.commit()
    db.refresh(subscription)
    return subscription
