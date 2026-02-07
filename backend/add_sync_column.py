#!/usr/bin/env python3

import sys
sys.path.append('.')

from app.database import SessionLocal
from sqlalchemy import text

def add_sync_column():
    """Add synced_to_sheets column to candidates table"""
    db = SessionLocal()
    try:
        # Check if column already exists
        result = db.execute(text("PRAGMA table_info(candidates)")).fetchall()
        columns = [row[1] for row in result]
        
        if 'synced_to_sheets' not in columns:
            print("Adding synced_to_sheets column...")
            db.execute(text("ALTER TABLE candidates ADD COLUMN synced_to_sheets BOOLEAN DEFAULT 0"))
            db.commit()
            print("Column added successfully!")
        else:
            print("Column already exists")
            
        # Verify column was added
        result = db.execute(text("PRAGMA table_info(candidates)")).fetchall()
        columns = [row[1] for row in result]
        print(f"Current columns: {columns}")
        
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    add_sync_column()