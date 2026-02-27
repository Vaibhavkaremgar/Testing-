"""
Database migration to add profile fields to User table
Run this script to update existing database
"""

from sqlalchemy import create_engine, text
from app.config import settings

def migrate():
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        # Add new columns if they don't exist
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN phone VARCHAR(50)"))
            print("✓ Added phone column")
        except Exception as e:
            print(f"Phone column already exists or error: {e}")
        
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN department VARCHAR(255)"))
            print("✓ Added department column")
        except Exception as e:
            print(f"Department column already exists or error: {e}")
        
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN bio TEXT"))
            print("✓ Added bio column")
        except Exception as e:
            print(f"Bio column already exists or error: {e}")
        
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN avatar_url VARCHAR(500)"))
            print("✓ Added avatar_url column")
        except Exception as e:
            print(f"Avatar_url column already exists or error: {e}")
        
        conn.commit()
    
    print("\n✅ Migration completed successfully!")

if __name__ == "__main__":
    migrate()
