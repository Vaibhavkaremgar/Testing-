from fastapi import Depends
from sqlalchemy.orm import Session

from app.auth import get_current_active_user
from app.database import get_db
from app.models import User
from app.usage_service import ensure_feature_limit_available


def enforce_usage_limit(feature_name: str, amount: int = 1):
    def dependency(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
    ):
        return ensure_feature_limit_available(db, current_user, feature_name, amount=amount)

    return dependency
