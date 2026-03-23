from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import List
from uuid import UUID
from app.database import get_db
from app.models import User
from app.schemas import Token, UserCreate, UserResponse, UserLogin, PasswordUpdate, UserUpdate, AdminUserUpdate
from app.auth import (
    get_password_hash,
    create_access_token,
    authenticate_user,
    get_current_active_user
)
from app.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse)
def register(user: UserCreate, db: Session = Depends(get_db)):
    # Check if user exists
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user with 15 trial credits
    hashed_password = get_password_hash(user.password)
    db_user = User(
        email=user.email,
        hashed_password=hashed_password,
        full_name=user.full_name,
        role=user.role,
        wallet_balance=15
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    # Log trial credit transaction
    from app.models import WalletTransaction, TransactionType
    trial_txn = WalletTransaction(
        user_id=db_user.id,
        amount=15,
        transaction_type=TransactionType.CREDIT,
        description="Trial credits",
        balance_after=15
    )
    db.add(trial_txn)
    db.commit()

    return db_user

@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Update last login via raw SQL (user object is not session-tracked)
    from datetime import datetime
    from sqlalchemy import text
    db.execute(text("UPDATE users SET last_login_at = :now WHERE id = :id"), {"now": datetime.utcnow(), "id": user.id})
    db.commit()
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    agency_id_str = str(user.agency_id) if user.agency_id else None
    access_token = create_access_token(
        data={
            "sub": user.email,
            "agency_id": agency_id_str,
            "role": user.role.value,
            "user_id": str(user.id),
            "full_name": user.full_name,
        },
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/login/json", response_model=Token)
def login_json(user_login: UserLogin, db: Session = Depends(get_db)):
    user = authenticate_user(db, user_login.email, user_login.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Update last login via raw SQL (user object is not session-tracked)
    from datetime import datetime
    from sqlalchemy import text
    db.execute(text("UPDATE users SET last_login_at = :now WHERE id = :id"), {"now": datetime.utcnow(), "id": user.id})
    db.commit()
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    agency_id_str = str(user.agency_id) if user.agency_id else None
    access_token = create_access_token(
        data={
            "sub": user.email,
            "agency_id": agency_id_str,
            "role": user.role.value,
            "user_id": str(user.id),
            "full_name": user.full_name,
        },
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_active_user)):
    return current_user

@router.post("/change-password")
def change_password(
    password_data: PasswordUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    from app.auth import verify_password
    
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    current_user.hashed_password = get_password_hash(password_data.new_password)
    db.commit()
    db.refresh(current_user)
    
    return {"message": "Password updated successfully", "success": True, "logout_required": True}

@router.put("/profile", response_model=UserResponse)
def update_profile(
    profile_data: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if profile_data.full_name:
        current_user.full_name = profile_data.full_name
    if profile_data.email:
        existing_user = db.query(User).filter(
            User.email == profile_data.email,
            User.id != current_user.id
        ).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use"
            )
        current_user.email = profile_data.email
    if profile_data.phone is not None:
        current_user.phone = profile_data.phone
    if profile_data.department is not None:
        current_user.department = profile_data.department
    if profile_data.bio is not None:
        current_user.bio = profile_data.bio
    
    db.commit()
    db.refresh(current_user)
    return current_user

@router.post("/profile/avatar")
def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    import os
    from pathlib import Path
    from PIL import Image
    import io
    
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif'}
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only image files are allowed (jpg, jpeg, png, gif)"
        )
    
    upload_dir = Path(settings.UPLOAD_DIR) / "avatars"
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Read and resize image
    image_data = file.file.read()
    image = Image.open(io.BytesIO(image_data))
    
    # Convert RGBA to RGB if needed
    if image.mode == 'RGBA':
        background = Image.new('RGB', image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[3])
        image = background
    
    # Resize to 200x200 maintaining aspect ratio and crop to square
    size = 200
    image.thumbnail((size * 2, size * 2), Image.Resampling.LANCZOS)
    
    # Crop to square from center
    width, height = image.size
    if width != height:
        min_dim = min(width, height)
        left = (width - min_dim) // 2
        top = (height - min_dim) // 2
        image = image.crop((left, top, left + min_dim, top + min_dim))
    
    # Final resize to exact 200x200
    image = image.resize((size, size), Image.Resampling.LANCZOS)
    
    # Save optimized image
    filename = f"user_{current_user.id}.jpg"
    file_path = upload_dir / filename
    image.save(file_path, 'JPEG', quality=90, optimize=True)
    
    current_user.avatar_url = f"/avatars/{filename}"
    db.commit()
    db.refresh(current_user)
    
    return {"avatar_url": current_user.avatar_url}

@router.get("/avatars/{filename}")
async def get_avatar(filename: str):
    from fastapi.responses import FileResponse
    from pathlib import Path
    import os
    
    file_path = Path(settings.UPLOAD_DIR) / "avatars" / filename
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Avatar not found")
    
    return FileResponse(file_path, media_type="image/jpeg")

# Admin endpoints
@router.get("/users/public")
def get_public_users(db: Session = Depends(get_db)):
    """Get super_admin and admin users only for tenant selection screen"""
    from sqlalchemy import text
    rows = db.execute(text(
        "SELECT id, full_name, email, role::text, agency_id FROM users WHERE is_active = true AND role::text IN ('super_admin', 'admin')"
    )).fetchall()
    return [{"id": r[0], "full_name": r[1], "email": r[2], "role": r[3], "agency_id": r[4]} for r in rows]

@router.get("/login-screen")
def get_login_screen(db: Session = Depends(get_db)):
    """Return super_admin user + all active agencies for the login screen"""
    from sqlalchemy import text
    super_admin = db.execute(text(
        "SELECT id, full_name, email, role::text FROM users WHERE is_active = true AND role::text = 'super_admin' LIMIT 1"
    )).fetchone()
    agencies = db.execute(text(
        "SELECT id, name, slug FROM agencies WHERE is_active = true ORDER BY name"
    )).fetchall()
    return {
        "super_admin": {"id": super_admin[0], "full_name": super_admin[1], "email": super_admin[2], "role": super_admin[3]} if super_admin else None,
        "agencies": [{"id": r[0], "name": r[1], "slug": r[2]} for r in agencies]
    }

@router.get("/users/by-agency/{agency_id}")
def get_users_by_agency(agency_id: UUID, db: Session = Depends(get_db)):
    """Get all users (admin + team members) for a specific agency"""
    from sqlalchemy import text
    rows = db.execute(text(
        "SELECT id, full_name, email, role::text FROM users WHERE is_active = true AND agency_id = :agency_id ORDER BY role::text, full_name"
    ), {"agency_id": agency_id}).fetchall()
    return [{"id": r[0], "full_name": r[1], "email": r[2], "role": r[3]} for r in rows]

@router.get("/users", response_model=List[UserResponse])
def get_all_users(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    from app.models import UserRole
    from datetime import datetime, timedelta
    
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can access this endpoint"
        )
    
    if current_user.role == UserRole.SUPER_ADMIN:
        users = db.query(User).all()
    else:
        users = db.query(User).filter(User.agency_id == current_user.agency_id).all()
    
    # Add online status based on last_login_at (online if logged in within last 15 minutes)
    result = []
    for user in users:
        user_dict = {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "phone": user.phone,
            "department": user.department,
            "bio": user.bio,
            "avatar_url": user.avatar_url,
            "is_active": user.is_active,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
            "last_login_at": user.last_login_at,
            "is_online": False
        }
        
        # Check if user is online (logged in within last 15 minutes)
        if user.last_login_at:
            time_diff = datetime.utcnow() - user.last_login_at
            user_dict["is_online"] = time_diff < timedelta(minutes=15)
        
        result.append(user_dict)
    
    return result

@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: UUID,
    user_data: AdminUserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    from app.models import UserRole
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can update users"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if user_data.full_name:
        user.full_name = user_data.full_name
    if user_data.email:
        existing = db.query(User).filter(
            User.email == user_data.email,
            User.id != user_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use"
            )
        user.email = user_data.email
    if user_data.role:
        user.role = user_data.role
    if user_data.is_active is not None:
        user.is_active = user_data.is_active
    
    db.commit()
    db.refresh(user)
    return user

@router.delete("/users/{user_id}")
def delete_user(
    user_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    from app.models import UserRole
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can delete users"
        )
    
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    db.delete(user)
    db.commit()
    return {"message": "User deleted successfully"}
