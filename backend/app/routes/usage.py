from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_active_user
from app.database import get_db
from app.models import User
from app.usage_schemas import UsageSummaryResponse
from app.usage_service import build_usage_summary

router = APIRouter(prefix="/usage", tags=["Usage"])


@router.get("/summary", response_model=UsageSummaryResponse)
def get_usage_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return build_usage_summary(db, current_user)
