#!/usr/bin/env python3

import sys
import os
import sqlite3

def migrate_database():
    db_path = os.path.join(os.path.dirname(__file__), 'talentai.db')
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if column exists
        cursor.execute("PRAGMA table_info(candidates)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'score_threshold' not in columns:
            # Add the new column
            cursor.execute("ALTER TABLE candidates ADD COLUMN score_threshold REAL")
            
            # Update existing records with default value
            cursor.execute("UPDATE candidates SET score_threshold = 60.0 WHERE score_threshold IS NULL")
            
            conn.commit()
            print("Successfully added score_threshold column and updated existing records")
        else:
            print("score_threshold column already exists")
            
    except Exception as e:
        print(f"Error migrating database: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()