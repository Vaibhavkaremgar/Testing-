import sqlite3

conn = sqlite3.connect('talentai.db')
cursor = conn.cursor()

try:
    # Add job_id column
    cursor.execute("ALTER TABLE job_descriptions ADD COLUMN job_id VARCHAR(50)")
    conn.commit()
    print("Added job_id column to job_descriptions table")
    
    # Verify
    cursor.execute("PRAGMA table_info(job_descriptions)")
    columns = cursor.fetchall()
    print("\nUpdated columns:")
    for col in columns:
        print(f"  {col[1]} ({col[2]})")
        
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("job_id column already exists")
    else:
        print(f"Error: {e}")
finally:
    conn.close()
