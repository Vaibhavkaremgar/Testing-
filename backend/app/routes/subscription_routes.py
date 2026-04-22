from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_active_user, get_current_admin_user
from app.database import get_db
from app.models import User
from app.subscription_schemas import SelectPlanRequest, SubscriptionResponse
from app.subscription_service import PLAN_CONFIG, get_active_subscription, select_plan

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


@router.get("/plans")
def get_plan_catalog():
    return PLAN_CONFIG


@router.get("/current", response_model=Optional[SubscriptionResponse])
def get_current_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    try:
        return get_active_subscription(db, current_user)
    except HTTPException as exc:
        if exc.status_code != 403:
            raise
        return None


@router.post("/select-plan", response_model=SubscriptionResponse)
def select_subscription_plan(
    payload: SelectPlanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    return select_plan(
        db=db,
        actor_user=current_user,
        user_id=payload.user_id,
        plan_name=payload.plan_name,
        billing_type=payload.billing_type,
        user_count=payload.user_count,
    )
