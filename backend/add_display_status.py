"""  
Migration script to add display_status column to candidates table
Run this once to update the database schema
"""
import sqlite3
import os

# Get database path
db_path = os.path.join(os.path.dirname(__file__), 'recruitment.db')

print(f"Database path: {db_path}")
print(f"Database exists: {os.path.exists(db_path)}")

# Connect to database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # Check if column exists
    cursor.execute("PRAGMA table_info(candidates)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'display_status' not in columns:
        # Add the new column
        cursor.execute("ALTER TABLE candidates ADD COLUMN display_status VARCHAR(50)")
        conn.commit()
        print("SUCCESS: Added display_status column to candidates table")
    else:
        print("INFO: display_status column already exists")
        
except Exception as e:
    print(f"ERROR: {e}")
    conn.rollback()
finally:
    conn.close()
