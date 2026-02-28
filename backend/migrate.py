"""
Run this script to add last_login_at column to users table
"""
from app.database import engine
from sqlalchemy import text

def migrate():
    try:
        with engine.connect() as conn:
            # Check if column exists
            result = conn.execute(text("PRAGMA table_info(users)"))
            columns = [row[1] for row in result]
            
            if 'last_login_at' not in columns:
                print("Adding last_login_at column...")
                conn.execute(text("ALTER TABLE users ADD COLUMN last_login_at TIMESTAMP"))
                conn.commit()
                print("✅ Migration completed successfully!")
            else:
                print("✅ Column already exists, skipping migration")
    except Exception as e:
        print(f"❌ Migration failed: {e}")

if __name__ == "__main__":
    migrate()
