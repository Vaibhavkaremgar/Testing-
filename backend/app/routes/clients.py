from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from uuid import UUID
from app.database import get_db
from app.models import Client, JobDescription, Candidate, User, CandidateStage, UserRole
from app.schemas import ClientCreate, ClientUpdate, ClientResponse, ClientStats
from app.auth import get_current_active_user, get_current_admin_user
from datetime import datetime, timedelta

router = APIRouter(prefix="/clients", tags=["Clients"])

@router.get("/stats")
def get_client_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    base_job_query = db.query(JobDescription)
    if current_user.role != UserRole.SUPER_ADMIN and current_user.agency_id:
        base_job_query = base_job_query.filter(JobDescription.agency_id == current_user.agency_id)

    total_clients = db.query(func.count(func.distinct(JobDescription.company_name))).select_from(
        base_job_query.subquery()
    ).scalar() or 0

    active_clients = db.query(func.count(func.distinct(JobDescription.company_name))).select_from(
        base_job_query.filter(JobDescription.is_active == True).subquery()
    ).scalar() or 0

    total_positions = db.query(func.sum(JobDescription.vacancies)).select_from(
        base_job_query.filter(JobDescription.is_active == True).subquery()
    ).scalar() or 0

    filled_positions = db.query(func.count(Candidate.id)).filter(
        Candidate.stage == CandidateStage.SELECTED
    ).scalar() or 0

    open_positions = max(0, total_positions - filled_positions)

    return {
        "total_clients": total_clients,
        "active_clients": active_clients,
        "total_positions": total_positions,
        "open_positions": open_positions,
        "filled_positions": filled_positions
    }

@router.get("/names")
def get_client_names(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    query = db.query(JobDescription.company_name).filter(
        JobDescription.company_name.isnot(None),
        JobDescription.company_name != ''
    )
    if current_user.agency_id:
        query = query.filter(JobDescription.agency_id == current_user.agency_id)
    company_names = query.distinct().all()
    return [name[0] for name in company_names]

@router.get("/count")
def get_clients_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    query = db.query(Client)
    if current_user.role != UserRole.SUPER_ADMIN and current_user.agency_id:
        query = query.filter(Client.agency_id == current_user.agency_id)
    return {"count": query.count()}

@router.get("", response_model=List[ClientResponse])
def get_clients(
    page: int = 1,
    limit: int = 100,
    agency_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    query = db.query(Client)
    if agency_id and current_user.role == UserRole.SUPER_ADMIN:
        query = query.filter(Client.agency_id == agency_id)
    elif current_user.agency_id:
        query = query.filter(Client.agency_id == current_user.agency_id)
    return query.offset((page - 1) * limit).limit(limit).all()

@router.post("", response_model=ClientResponse)
def create_client(
    client: ClientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    db_client = Client(**client.model_dump())
    db_client.agency_id = current_user.agency_id
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client

@router.put("/{client_id}", response_model=ClientResponse)
def update_client(
    client_id: UUID,
    client_update: ClientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    db_client = db.query(Client).filter(Client.id == client_id).first()
    if not db_client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    update_data = client_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_client, field, value)
    
    db.commit()
    db.refresh(db_client)
    return db_client

@router.delete("/{client_id}")
def delete_client(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    db_client = db.query(Client).filter(Client.id == client_id).first()
    if not db_client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    db.delete(db_client)
    db.commit()
    return {"message": "Client deleted successfully"}
