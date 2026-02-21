from app.database import SessionLocal
from app.models import User
from app.auth import get_password_hash, verify_password

db = SessionLocal()

# Find or create admin user
admin = db.query(User).filter(User.email == "admin@example.com").first()

if admin:
    print("✅ Admin user found!")
    print(f"Email: {admin.email}")
    print(f"Active: {admin.is_active}")
    
    # Reset password
    new_password = "admin123"
    admin.hashed_password = get_password_hash(new_password)
    admin.is_active = True
    db.commit()
    
    print("\n✅ Password reset successfully!")
    print(f"Email: admin@example.com")
    print(f"Password: {new_password}")
    
    # Verify the password works
    db.refresh(admin)
    if verify_password(new_password, admin.hashed_password):
        print("\n✅ Password verification: SUCCESS")
    else:
        print("\n❌ Password verification: FAILED")
else:
    print("❌ Admin user not found. Creating new one...")
    
    admin = User(
        email="admin@example.com",
        hashed_password=get_password_hash("admin123"),
        full_name="Admin User",
        role="admin",
        is_active=True
    )
    
    db.add(admin)
    db.commit()
    
    print("✅ Admin user created!")
    print("Email: admin@example.com")
    print("Password: admin123")

db.close()

print("\n" + "="*50)
print("Now try logging in with:")
print("Email: admin@example.com")
print("Password: admin123")
print("="*50)
