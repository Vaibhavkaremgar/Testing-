from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import User, UserRole
from app.auth import get_password_hash

def seed_database():
    db = SessionLocal()
    
    try:
        # Check if already seeded
        if db.query(User).first():
            return
        
        # Create demo users
        users = [
            User(
                email="admin@talentai.com",
                hashed_password=get_password_hash("admin123"),
                full_name="Admin User",
                role=UserRole.ADMIN
            ),
            User(
                email="recruiter@talentai.com",
                hashed_password=get_password_hash("recruiter123"),
                full_name="Sarah Johnson",
                role=UserRole.RECRUITER
            ),
            User(
                email="manager@talentai.com",
                hashed_password=get_password_hash("manager123"),
                full_name="Mike Chen",
                role=UserRole.HIRING_MANAGER
            ),
        ]
        for user in users:
            db.add(user)
        db.commit()
        
        print("Database seeded with users only (no demo data)")
        
    except Exception as e:
        print(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
