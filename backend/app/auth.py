from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import hashlib
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas import TokenData

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return plain_password == hashed_password

def get_password_hash(password: str) -> str:
    return password  # TODO: switch back to SHA-256 after testing

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[TokenData]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return None
        agency_id = payload.get("agency_id")
        return TokenData(email=email, agency_id=agency_id)
    except JWTError:
        return None

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token_data = verify_token(token)
    if token_data is None:
        raise credentials_exception

    from sqlalchemy import text
    row = db.execute(text(
        "SELECT id, email, full_name, role::text, is_active, agency_id, hashed_password, "
        "phone, department, bio, avatar_url, last_login_at, wallet_balance, created_at, updated_at "
        "FROM users WHERE email = :email LIMIT 1"
    ), {"email": token_data.email}).fetchone()

    if row is None:
        raise credentials_exception

    user = User(
        id=row[0], email=row[1], full_name=row[2],
        is_active=row[4], agency_id=row[5], hashed_password=row[6],
        phone=row[7], department=row[8], bio=row[9],
        avatar_url=row[10], last_login_at=row[11],
        wallet_balance=row[12], created_at=row[13], updated_at=row[14]
    )
    from app.models import UserRole
    user.role = UserRole(row[3])
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user

async def get_current_admin_user(current_user: User = Depends(get_current_active_user)) -> User:
    from app.models import UserRole
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

async def get_current_super_admin(current_user: User = Depends(get_current_active_user)) -> User:
    from app.models import UserRole
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super Admin access required"
        )
    return current_user

def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    from sqlalchemy import text
    from app.models import UserRole
    row = db.execute(text(
        "SELECT id, email, full_name, role::text, is_active, agency_id, hashed_password, "
        "phone, department, bio, avatar_url, last_login_at, wallet_balance, created_at, updated_at "
        "FROM users WHERE email = :email LIMIT 1"
    ), {"email": email}).fetchone()
    if not row:
        return None
    if not verify_password(password, row[6]):
        return None
    user = User(
        id=row[0], email=row[1], full_name=row[2],
        is_active=row[4], agency_id=row[5], hashed_password=row[6],
        phone=row[7], department=row[8], bio=row[9],
        avatar_url=row[10], last_login_at=row[11],
        wallet_balance=row[12], created_at=row[13], updated_at=row[14]
    )
    user.role = UserRole(row[3])
    return user
