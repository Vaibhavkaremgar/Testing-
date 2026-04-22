from fastapi import Depends
from sqlalchemy.orm import Session

from app.auth import get_current_active_user
from app.database import get_db
from app.models import User
from app.subscription_service import get_validated_subscription


def enforce_plan(feature: str):
    def dependency(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
    ):
        return get_validated_subscription(db, current_user, feature)

    return dependency
