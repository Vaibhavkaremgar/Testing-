"""
Add internal_notes column to candidates table
"""

from sqlalchemy import create_engine, text
from app.config import settings

def migrate():
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE candidates ADD COLUMN internal_notes TEXT"))
            conn.commit()
            print("✓ Added internal_notes column to candidates")
        except Exception as e:
            print(f"internal_notes column already exists or error: {e}")
    
    print("\n✅ Migration completed!")

if __name__ == "__main__":
    migrate()
