from app.auth import get_password_hash
from app.database import SessionLocal
from app.models import User

db = SessionLocal()

# Get admin user
user = db.query(User).filter(User.email == 'admin@talentai.com').first()

if user:
    # Update password
    user.hashed_password = get_password_hash('admin123')
    db.commit()
    print('Password updated successfully!')
    print('Email: admin@talentai.com')
    print('Password: admin123')
else:
    print('User not found')

db.close()
