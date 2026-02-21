from app.database import SessionLocal
from app.models import User
from app.auth import get_password_hash, verify_password, authenticate_user

db = SessionLocal()

# Test credentials
test_email = "admin@example.com"
test_password = "admin123"

print("="*60)
print("AUTHENTICATION DEBUG")
print("="*60)

# Check if user exists
user = db.query(User).filter(User.email == test_email).first()

if not user:
    print("❌ User not found! Creating...")
    user = User(
        email=test_email,
        hashed_password=get_password_hash(test_password),
        full_name="Admin User",
        role="admin",
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    print("✅ User created!")

print(f"\nUser Details:")
print(f"  Email: {user.email}")
print(f"  Active: {user.is_active}")
print(f"  Role: {user.role}")
print(f"  Hashed Password: {user.hashed_password[:20]}...")

# Test password hashing
print(f"\nPassword Testing:")
test_hash = get_password_hash(test_password)
print(f"  Input Password: {test_password}")
print(f"  Generated Hash: {test_hash[:20]}...")
print(f"  Stored Hash: {user.hashed_password[:20]}...")
print(f"  Hashes Match: {test_hash == user.hashed_password}")

# Test verify_password function
verify_result = verify_password(test_password, user.hashed_password)
print(f"  verify_password(): {verify_result}")

# Test authenticate_user function
auth_user = authenticate_user(db, test_email, test_password)
print(f"  authenticate_user(): {'✅ SUCCESS' if auth_user else '❌ FAILED'}")

if not auth_user:
    print("\n⚠️  Authentication failed! Resetting password...")
    user.hashed_password = get_password_hash(test_password)
    db.commit()
    db.refresh(user)
    
    # Test again
    auth_user = authenticate_user(db, test_email, test_password)
    print(f"  After reset: {'✅ SUCCESS' if auth_user else '❌ STILL FAILED'}")

db.close()

print("\n" + "="*60)
print("LOGIN CREDENTIALS:")
print(f"  Email: {test_email}")
print(f"  Password: {test_password}")
print("="*60)
