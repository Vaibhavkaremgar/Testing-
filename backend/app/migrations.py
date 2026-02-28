"""
Auto-migration script - runs on startup
"""
from app.database import engine
from sqlalchemy import text, inspect

def run_migrations():
    """Run all pending migrations"""
    try:
        inspector = inspect(engine)
        
        with engine.connect() as conn:
            # Check if last_login_at column exists
            columns = [col['name'] for col in inspector.get_columns('users')]
            
            if 'last_login_at' not in columns:
                print("🔄 Running migration: Adding last_login_at column...")
                conn.execute(text("ALTER TABLE users ADD COLUMN last_login_at TIMESTAMP"))
                conn.commit()
                print("✅ Migration completed: last_login_at column added")
            else:
                print("✅ Database is up to date")
                
    except Exception as e:
        print(f"⚠️ Migration warning: {e}")
        # Don't fail startup if migration fails

if __name__ == "__main__":
    run_migrations()
