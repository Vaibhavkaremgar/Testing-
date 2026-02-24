"""
Migration script to add stage_entered_at and applied_at columns to candidates table
Run this once to update existing database
"""
import sqlite3
import os
from datetime import datetime

def migrate():
    # Try to find the database file
    db_paths = [
        'recruitment.db',
        '../recruitment.db',
        'app/recruitment.db'
    ]
    
    db_path = None
    for path in db_paths:
        if os.path.exists(path):
            db_path = path
            break
    
    if not db_path:
        print("Database file not found. It will be created when you start the backend.")
        print("Run this migration after starting the backend at least once.")
        return
    
    print(f"Using database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(candidates)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Add stage_entered_at if not exists
        if 'stage_entered_at' not in columns:
            print("Adding stage_entered_at column...")
            cursor.execute("""
                ALTER TABLE candidates 
                ADD COLUMN stage_entered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            """)
            # Set stage_entered_at to stage_updated_at for existing records
            cursor.execute("""
                UPDATE candidates 
                SET stage_entered_at = stage_updated_at 
                WHERE stage_entered_at IS NULL
            """)
            print("stage_entered_at column added")
        else:
            print("stage_entered_at column already exists")
        
        # Add applied_at if not exists
        if 'applied_at' not in columns:
            print("Adding applied_at column...")
            cursor.execute("""
                ALTER TABLE candidates 
                ADD COLUMN applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            """)
            # Set applied_at to created_at for existing records
            cursor.execute("""
                UPDATE candidates 
                SET applied_at = created_at 
                WHERE applied_at IS NULL
            """)
            print("applied_at column added")
        else:
            print("applied_at column already exists")
        
        conn.commit()
        print("\nMigration completed successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"\nMigration failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
