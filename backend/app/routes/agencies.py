from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from app.database import get_db
from app.models import Agency, User, UserRole
from app.schemas import AgencyWithAdminCreate, AgencyUpdate, AgencyResponse
from app.auth import get_current_super_admin, get_password_hash

router = APIRouter(prefix="/agencies", tags=["Agencies"])


@router.get("", response_model=List[AgencyResponse])
def get_agencies(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin)
):
    return db.query(Agency).order_by(Agency.name).all()


@router.get("/{agency_id}", response_model=AgencyResponse)
def get_agency(
    agency_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin)
):
    agency = db.query(Agency).filter(Agency.id == agency_id).first()
    if not agency:
        raise HTTPException(status_code=404, detail="Agency not found")
    return agency


@router.post("", response_model=AgencyResponse)
def create_agency(
    payload: AgencyWithAdminCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin)
):
    if db.query(Agency).filter(Agency.slug == payload.slug).first():
        raise HTTPException(status_code=400, detail="Agency slug already exists")
    if db.query(User).filter(User.email == payload.admin_email).first():
        raise HTTPException(status_code=400, detail="Admin email already registered")

    db_agency = Agency(name=payload.name, slug=payload.slug, is_active=payload.is_active)
    db.add(db_agency)
    db.flush()  # get db_agency.id without committing

    admin_user = User(
        email=payload.admin_email,
        hashed_password=get_password_hash(payload.admin_password),
        full_name=payload.admin_full_name,
        role=UserRole.ADMIN,
        agency_id=db_agency.id,
        wallet_balance=0,
        is_active=True
    )
    db.add(admin_user)
    db.commit()
    db.refresh(db_agency)
    return db_agency


@router.put("/{agency_id}", response_model=AgencyResponse)
def update_agency(
    agency_id: UUID,
    agency_update: AgencyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin)
):
    db_agency = db.query(Agency).filter(Agency.id == agency_id).first()
    if not db_agency:
        raise HTTPException(status_code=404, detail="Agency not found")
    for field, value in agency_update.model_dump(exclude_unset=True).items():
        setattr(db_agency, field, value)
    db.commit()
    db.refresh(db_agency)
    return db_agency


@router.delete("/{agency_id}")
def delete_agency(
    agency_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin)
):
    db_agency = db.query(Agency).filter(Agency.id == agency_id).first()
    if not db_agency:
        raise HTTPException(status_code=404, detail="Agency not found")
    db.delete(db_agency)
    db.commit()
    return {"message": "Agency deleted successfully"}
