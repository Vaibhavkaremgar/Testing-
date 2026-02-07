from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import User, UserRole
from app.auth import get_password_hash

def create_admin_user():
    db = SessionLocal()
    
    try:
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == "admin@talentai.com").first()
        if existing_user:
            print("Admin user already exists!")
            print("\nLogin Credentials:")
            print("Email: admin@talentai.com")
            print("Password: admin123")
            return
        
        # Create admin user
        admin_user = User(
            email="admin@talentai.com",
            hashed_password=get_password_hash("admin123"),
            full_name="Admin User",
            role=UserRole.ADMIN
        )
        
        db.add(admin_user)
        db.commit()
        
        print("[SUCCESS] Admin user created!")
        print("\nLogin Credentials:")
        print("=" * 40)
        print("Email: admin@talentai.com")
        print("Password: admin123")
        print("=" * 40)
        print("\nYou can now login to the dashboard.")
        
    except Exception as e:
        print(f"Error creating admin user: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_admin_user()
