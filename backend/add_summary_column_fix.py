import sqlite3
import os

# Path to your database
db_path = "recruitment.db"

if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    exit(1)

# Connect to database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # Check if summary column exists
    cursor.execute("PRAGMA table_info(candidates)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'summary' not in columns:
        print("Adding 'summary' column to candidates table...")
        cursor.execute("ALTER TABLE candidates ADD COLUMN summary TEXT")
        conn.commit()
        print("✓ Successfully added 'summary' column")
    else:
        print("✓ 'summary' column already exists")
    
except Exception as e:
    print(f"Error: {e}")
    conn.rollback()
finally:
    conn.close()

print("\nMigration complete!")
