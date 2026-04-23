from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth import get_current_user
from app.models import User, WalletTransaction, TransactionType
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

class CreateOrderRequest(BaseModel):
    credits: int
    payment_method: str  # razorpay, stripe, upi

class PaymentSuccessRequest(BaseModel):
    order_id: str
    transaction_id: str
    credits: int
    payment_method: str
    amount_paid: float

@router.post("/wallet/create-order")
async def create_order(
    request: CreateOrderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Price calculation: 1 credit = ₹10
    price = request.credits * 10
    
    # Create order ID
    order_id = f"ORD_{current_user.id}_{int(datetime.now().timestamp())}"
    
    return {
        "order_id": order_id,
        "credits": request.credits,
        "price": price,
        "currency": "INR",
        "payment_method": request.payment_method
    }

@router.post("/wallet/payment-success")
async def payment_success(
    request: PaymentSuccessRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_user = db.query(User).filter(User.id == current_user.id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update wallet balance
    db_user.wallet_balance += request.credits
    
    # Create transaction record
    transaction = WalletTransaction(
        user_id=db_user.id,
        amount=request.credits,
        transaction_type=TransactionType.CREDIT,
        description=f"Purchased {request.credits} credits via {request.payment_method}",
        balance_after=db_user.wallet_balance,
    )
    
    db.add(transaction)
    db.commit()
    db.refresh(db_user)
    
    return {
        "success": True,
        "new_balance": db_user.wallet_balance,
        "transaction_id": transaction.id
    }
