from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from app.database import get_db
from app.models import User, WalletTransaction, TransactionType, UserRole
from app.auth import get_current_active_user
from pydantic import BaseModel

router = APIRouter(prefix="/wallet", tags=["Wallet"])

class AddCreditsRequest(BaseModel):
    user_id: int
    amount: float
    description: str

class TransactionResponse(BaseModel):
    id: int
    amount: float
    transaction_type: str
    description: str
    balance_after: float
    created_at: datetime

@router.get("/balance")
def get_wallet_balance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get current user's wallet balance"""
    return {"balance": current_user.wallet_balance or 0.0}

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
    """Add credits to user wallet (Admin only)"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only admins can add credits")
    
    user = db.query(User).filter(User.id == request.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update balance
    user.wallet_balance = (user.wallet_balance or 0.0) + request.amount
    
    # Create transaction record
    transaction = WalletTransaction(
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
        "new_balance": user.wallet_balance,
        "transaction_id": transaction.id
    }

@router.get("/all-users")
def get_all_users_wallets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all users with wallet balances (Admin only)"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only admins can view all wallets")
    
    users = db.query(User).all()
    return [
        {
            "id": u.id,
            "full_name": u.full_name,
            "email": u.email,
            "role": u.role.value,
            "wallet_balance": u.wallet_balance or 0.0
        }
        for u in users
    ]
