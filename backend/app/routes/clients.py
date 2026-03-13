from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
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
    # Total Clients = Unique company names in jobs
    total_clients = db.query(func.count(func.distinct(JobDescription.company_name))).scalar() or 0
    
    # Active Clients = Unique company names in active jobs
    active_clients = db.query(func.count(func.distinct(JobDescription.company_name))).filter(
        JobDescription.is_active == True
    ).scalar() or 0
    
    # Total Positions = Sum of vacancies from ACTIVE jobs only
    total_positions = db.query(func.sum(JobDescription.vacancies)).filter(
        JobDescription.is_active == True
    ).scalar() or 0
    
    # Filled Positions = Count of candidates in SELECTED stage
    filled_positions = db.query(func.count(Candidate.id)).filter(
        Candidate.stage == CandidateStage.SELECTED
    ).scalar() or 0
    
    # Open Positions = Total Positions - Filled Positions
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
    # Get unique company names from jobs
    company_names = db.query(JobDescription.company_name).filter(
        JobDescription.company_name.isnot(None),
        JobDescription.company_name != ''
    ).distinct().all()
    return [name[0] for name in company_names]

@router.get("", response_model=List[ClientResponse])
def get_clients(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    clients = db.query(Client).offset(skip).limit(limit).all()
    return clients

@router.post("", response_model=ClientResponse)
def create_client(
    client: ClientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    db_client = Client(**client.model_dump())
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client

@router.put("/{client_id}", response_model=ClientResponse)
def update_client(
    client_id: int,
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
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    db_client = db.query(Client).filter(Client.id == client_id).first()
    if not db_client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    db.delete(db_client)
    db.commit()
    return {"message": "Client deleted successfully"}
