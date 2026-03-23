from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID
from app.database import get_db
from app.models import AgencyDiscount, Agency, UserRole
from app.auth import get_current_active_user
from pydantic import BaseModel

router = APIRouter(prefix="/pricing", tags=["Pricing"])


class DiscountUpsert(BaseModel):
    agency_id: UUID
    discount_type: str  # 'percentage' or 'amount'
    discount_value: float
    currency: Optional[str] = "USD"


def require_super_admin(current_user=Depends(get_current_active_user)):
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Super admin only")
    return current_user


@router.get("/agencies")
def list_agencies(
    db: Session = Depends(get_db),
    current_user=Depends(require_super_admin)
):
    from app.models import Agency
    agencies = db.query(Agency).order_by(Agency.name).all()
    return [{"id": str(a.id), "name": a.name} for a in agencies]


@router.get("/discounts")
def get_all_discounts(
    db: Session = Depends(get_db),
    current_user=Depends(require_super_admin)
):
    discounts = db.query(AgencyDiscount).all()
    agencies = db.query(Agency).all()
    agency_map = {str(a.id): a.name for a in agencies}

    return [
        {
            "id": d.id,
            "agency_id": str(d.agency_id),
            "agency_name": agency_map.get(str(d.agency_id), "Unknown"),
            "discount_type": d.discount_type,
            "discount_value": d.discount_value,
            "currency": d.currency,
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "updated_at": d.updated_at.isoformat() if d.updated_at else None,
        }
        for d in discounts
    ]


@router.get("/discounts/agency/{agency_id}")
def get_agency_discount(
    agency_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user)
):
    # Agency admin can fetch their own discount; super admin can fetch any
    if current_user.role != UserRole.SUPER_ADMIN:
        if str(current_user.agency_id) != str(agency_id):
            raise HTTPException(status_code=403, detail="Forbidden")

    discount = db.query(AgencyDiscount).filter(AgencyDiscount.agency_id == agency_id).first()
    if not discount:
        return None
    return {
        "id": discount.id,
        "agency_id": str(discount.agency_id),
        "discount_type": discount.discount_type,
        "discount_value": discount.discount_value,
        "currency": discount.currency,
    }


@router.post("/discounts")
def upsert_discount(
    payload: DiscountUpsert,
    db: Session = Depends(get_db),
    current_user=Depends(require_super_admin)
):
    if payload.discount_type not in ("percentage", "amount"):
        raise HTTPException(status_code=400, detail="discount_type must be 'percentage' or 'amount'")
    if payload.discount_value <= 0:
        raise HTTPException(status_code=400, detail="discount_value must be positive")
    if payload.discount_type == "percentage" and payload.discount_value > 100:
        raise HTTPException(status_code=400, detail="Percentage cannot exceed 100")

    agency = db.query(Agency).filter(Agency.id == payload.agency_id).first()
    if not agency:
        raise HTTPException(status_code=404, detail="Agency not found")

    existing = db.query(AgencyDiscount).filter(AgencyDiscount.agency_id == payload.agency_id).first()
    if existing:
        existing.discount_type = payload.discount_type
        existing.discount_value = payload.discount_value
        existing.currency = payload.currency
        existing.set_by_user_id = current_user.id
    else:
        existing = AgencyDiscount(
            agency_id=payload.agency_id,
            discount_type=payload.discount_type,
            discount_value=payload.discount_value,
            currency=payload.currency,
            set_by_user_id=current_user.id,
        )
        db.add(existing)

    db.commit()
    db.refresh(existing)
    return {"success": True, "id": existing.id}


@router.delete("/discounts/{agency_id}")
def delete_discount(
    agency_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_super_admin)
):
    discount = db.query(AgencyDiscount).filter(AgencyDiscount.agency_id == agency_id).first()
    if not discount:
        raise HTTPException(status_code=404, detail="No discount found for this agency")
    db.delete(discount)
    db.commit()
    return {"success": True}
