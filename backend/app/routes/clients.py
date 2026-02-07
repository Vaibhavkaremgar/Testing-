from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from app.database import get_db
from app.models import Client, JobDescription, Candidate, User, CandidateStage
from app.schemas import ClientCreate, ClientUpdate, ClientResponse, ClientStats
from app.auth import get_current_active_user
from datetime import datetime, timedelta

router = APIRouter(prefix="/clients", tags=["Clients"])

@router.get("/stats")
def get_client_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    total_clients = db.query(func.count(Client.id)).scalar()
    active_clients = db.query(func.count(Client.id)).filter(Client.is_active == True).scalar()
    total_positions = db.query(func.sum(Client.total_positions)).scalar() or 0
    open_positions = db.query(func.sum(Client.positions_open)).scalar() or 0
    filled_positions = db.query(func.sum(Client.positions_filled)).scalar() or 0
    
    return {
        "total_clients": total_clients,
        "active_clients": active_clients,
        "total_positions": total_positions,
        "open_positions": open_positions,
        "filled_positions": filled_positions
    }

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
    current_user: User = Depends(get_current_active_user)
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
    current_user: User = Depends(get_current_active_user)
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
    current_user: User = Depends(get_current_active_user)
):
    db_client = db.query(Client).filter(Client.id == client_id).first()
    if not db_client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    db.delete(db_client)
    db.commit()
    return {"message": "Client deleted successfully"}
