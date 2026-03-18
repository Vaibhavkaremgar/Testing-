from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import Agency, User
from app.schemas import AgencyCreate, AgencyUpdate, AgencyResponse
from app.auth import get_current_super_admin

router = APIRouter(prefix="/agencies", tags=["Agencies"])


@router.get("", response_model=List[AgencyResponse])
def get_agencies(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin)
):
    return db.query(Agency).order_by(Agency.name).all()


@router.get("/{agency_id}", response_model=AgencyResponse)
def get_agency(
    agency_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin)
):
    agency = db.query(Agency).filter(Agency.id == agency_id).first()
    if not agency:
        raise HTTPException(status_code=404, detail="Agency not found")
    return agency


@router.post("", response_model=AgencyResponse)
def create_agency(
    agency: AgencyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin)
):
    existing = db.query(Agency).filter(Agency.slug == agency.slug).first()
    if existing:
        raise HTTPException(status_code=400, detail="Agency slug already exists")
    db_agency = Agency(**agency.model_dump())
    db.add(db_agency)
    db.commit()
    db.refresh(db_agency)
    return db_agency


@router.put("/{agency_id}", response_model=AgencyResponse)
def update_agency(
    agency_id: int,
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
    agency_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin)
):
    db_agency = db.query(Agency).filter(Agency.id == agency_id).first()
    if not db_agency:
        raise HTTPException(status_code=404, detail="Agency not found")
    db.delete(db_agency)
    db.commit()
    return {"message": "Agency deleted successfully"}
