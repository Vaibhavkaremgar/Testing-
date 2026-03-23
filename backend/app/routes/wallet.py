from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from uuid import UUID
from app.database import get_db
from app.models import Agency, User, WalletTransaction, TransactionType, UserRole
from app.auth import get_current_active_user
from pydantic import BaseModel

router = APIRouter(prefix="/wallet", tags=["Wallet"])

class AddCreditsRequest(BaseModel):
    user_id: UUID | None = None
    agency_id: UUID | None = None
    amount: int
    description: str

class TransactionResponse(BaseModel):
    id: int
    amount: float
    transaction_type: str
    description: str
    balance_after: float
    created_at: datetime


def _get_agency_admin(db: Session, agency_id: UUID):
    agency = db.query(Agency).filter(Agency.id == agency_id).first()
    if not agency:
        raise HTTPException(status_code=404, detail="Agency not found")

    admin_user = db.query(User).filter(
        User.agency_id == agency_id,
        User.role == UserRole.ADMIN,
        User.is_active == True
    ).first()
    if not admin_user:
        raise HTTPException(status_code=404, detail="Agency admin not found")

    return agency, admin_user

@router.get("/balance")
def get_wallet_balance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get current user's wallet balance in credits"""
    return {"balance": current_user.wallet_balance or 0}

@router.get("/transactions")
def get_transactions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get user's transaction history"""
    transactions = db.query(WalletTransaction).filter(
        WalletTransaction.user_id == current_user.id
    ).order_by(WalletTransaction.created_at.desc()).all()
    
    return [
        {
            "id": t.id,
            "amount": t.amount,
            "transaction_type": t.transaction_type.value,
            "description": t.description,
            "balance_after": t.balance_after,
            "created_at": t.created_at.isoformat()
        }
        for t in transactions
    ]

@router.post("/add-credits")
def add_credits(
    request: AddCreditsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Add credits to a user or agency admin wallet"""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Only admins can add credits")

    if not request.user_id and not request.agency_id:
        raise HTTPException(status_code=400, detail="Either user_id or agency_id is required")

    if request.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than 0")

    user = None
    agency = None

    if request.agency_id:
        agency, user = _get_agency_admin(db, request.agency_id)
        if current_user.role == UserRole.ADMIN and current_user.agency_id != request.agency_id:
            raise HTTPException(status_code=403, detail="You can only add credits within your agency")
    elif request.user_id:
        user = db.query(User).filter(User.id == request.user_id).first()
        if current_user.role == UserRole.ADMIN and user and user.agency_id != current_user.agency_id:
            raise HTTPException(status_code=403, detail="You can only add credits within your agency")

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update balance
    user.wallet_balance = (user.wallet_balance or 0) + request.amount

    # Create transaction record
    transaction = WalletTransaction(
        agency_id=agency.id if agency else user.agency_id,
        user_id=user.id,
        amount=request.amount,
        transaction_type=TransactionType.CREDIT,
        description=request.description,
        balance_after=user.wallet_balance
    )
    db.add(transaction)
    db.commit()
    
    return {
        "success": True,
        "agency_id": str(agency.id) if agency else (str(user.agency_id) if user.agency_id else None),
        "agency_name": agency.name if agency else None,
        "user_id": str(user.id),
        "user_name": user.full_name,
        "new_balance": user.wallet_balance,
        "transaction_id": transaction.id
    }


@router.get("/agency-admin/{agency_id}")
def get_agency_admin_wallet(
    agency_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get agency admin wallet details for super admin or the same agency admin"""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Only admins can view agency wallet details")

    if current_user.role == UserRole.ADMIN and current_user.agency_id != agency_id:
        raise HTTPException(status_code=403, detail="You can only view your agency wallet details")

    agency, admin_user = _get_agency_admin(db, agency_id)
    transactions = db.query(WalletTransaction).filter(
        WalletTransaction.user_id == admin_user.id
    ).order_by(WalletTransaction.created_at.desc()).limit(20).all()

    return {
        "agency": {
            "id": str(agency.id),
            "name": agency.name,
            "slug": agency.slug,
        },
        "admin": {
            "id": str(admin_user.id),
            "full_name": admin_user.full_name,
            "email": admin_user.email,
            "wallet_balance": admin_user.wallet_balance or 0,
        },
        "transactions": [
            {
                "id": t.id,
                "amount": t.amount,
                "transaction_type": t.transaction_type.value,
                "description": t.description,
                "balance_after": t.balance_after,
                "created_at": t.created_at.isoformat()
            }
            for t in transactions
        ]
    }

@router.get("/all-users")
def get_all_users_wallets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all users with wallet balances (Admin only)"""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Only admins can view all wallets")

    query = db.query(User)
    if current_user.agency_id:
        query = query.filter(User.agency_id == current_user.agency_id)
    users = query.all()
    return [
        {
            "id": u.id,
            "full_name": u.full_name,
            "email": u.email,
            "role": u.role.value,
            "wallet_balance": u.wallet_balance or 0
        }
        for u in users
    ]
