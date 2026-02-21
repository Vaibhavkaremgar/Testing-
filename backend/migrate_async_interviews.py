import sqlite3
import os

def migrate_database():
    """Add async interview fields to database"""
    db_path = "recruitment.db"
    
    if not os.path.exists(db_path):
        print("Database doesn't exist yet")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if interviews table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='interviews'")
    if not cursor.fetchone():
        print("Interviews table doesn't exist yet")
        conn.close()
        return
    
    # Get existing columns
    cursor.execute("PRAGMA table_info(interviews)")
    columns = [col[1] for col in cursor.fetchall()]
    
    # Add new columns if they don't exist
    new_columns = [
        ("is_async", "BOOLEAN DEFAULT 0"),
        ("async_link", "VARCHAR(500)"),
        ("async_token", "VARCHAR(255)"),
        ("async_expires_at", "DATETIME"),
        ("async_started_at", "DATETIME"),
        ("async_completed_at", "DATETIME"),
        ("async_answers", "TEXT")
    ]
    
    for col_name, col_type in new_columns:
        if col_name not in columns:
            print(f"Adding column: {col_name}")
            cursor.execute(f"ALTER TABLE interviews ADD COLUMN {col_name} {col_type}")
            conn.commit()
    
    # Check job_descriptions table
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='job_descriptions'")
    if cursor.fetchone():
        cursor.execute("PRAGMA table_info(job_descriptions)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if "interview_questions" not in columns:
            print("Adding interview_questions column to job_descriptions")
            cursor.execute("ALTER TABLE job_descriptions ADD COLUMN interview_questions TEXT")
            conn.commit()
    
    conn.close()
    print("Migration complete")

if __name__ == "__main__":
    migrate_database()
