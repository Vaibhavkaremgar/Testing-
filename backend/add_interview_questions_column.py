"""
Quick migration script to add interview_questions column to job_descriptions table
Run this with: python add_interview_questions_column.py
"""
import sqlite3
import os

# Path to your database
DB_PATH = os.path.join(os.path.dirname(__file__), "recruitment.db")

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(job_descriptions)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'interview_questions' not in columns:
            print("Adding interview_questions column...")
            cursor.execute("""
                ALTER TABLE job_descriptions 
                ADD COLUMN interview_questions JSON
            """)
            conn.commit()
            print("✓ Column added successfully!")
        else:
            print("✓ Column already exists!")
        
        # Verify
        cursor.execute("SELECT COUNT(*) FROM job_descriptions")
        count = cursor.fetchone()[0]
        print(f"✓ Found {count} jobs in database")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print(f"✗ Database not found at: {DB_PATH}")
        print("Please check the path and try again.")
    else:
        print(f"Database found at: {DB_PATH}")
        migrate()
