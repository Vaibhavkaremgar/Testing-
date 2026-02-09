"""
Migration script to add display_status column to candidates table
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine
from sqlalchemy import text

def migrate():
    with engine.connect() as conn:
        try:
            # Check if column exists
            result = conn.execute(text("PRAGMA table_info(candidates)"))
            columns = [row[1] for row in result]
            
            if 'display_status' not in columns:
                # Add the new column
                conn.execute(text("ALTER TABLE candidates ADD COLUMN display_status VARCHAR(50)"))
                conn.commit()
                print("SUCCESS: Added display_status column to candidates table")
            else:
                print("INFO: display_status column already exists")
                
        except Exception as e:
            print(f"ERROR: {e}")
            conn.rollback()

if __name__ == "__main__":
    migrate()
