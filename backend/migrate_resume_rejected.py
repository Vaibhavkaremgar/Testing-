"""
Migration script to convert RESUME_REJECTED to REJECTED in Railway database
Run this once after deployment
"""
import sqlite3
import os

# Railway database path
db_path = os.getenv("DATABASE_URL", "sqlite:///./app.db").replace("sqlite:///", "")

print(f"Connecting to database: {db_path}")

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if candidates table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='candidates'")
    if not cursor.fetchone():
        print("❌ Candidates table doesn't exist yet")
        exit(0)
    
    # Count candidates with resume_rejected stage
    cursor.execute("SELECT COUNT(*) FROM candidates WHERE stage = 'resume_rejected'")
    count = cursor.fetchone()[0]
    
    if count > 0:
        print(f"⚠️  Found {count} candidates with 'resume_rejected' stage")
        print("🔄 Converting to 'rejected'...")
        
        # Update resume_rejected to rejected
        cursor.execute("UPDATE candidates SET stage = 'rejected' WHERE stage = 'resume_rejected'")
        conn.commit()
        
        print(f"✅ Successfully converted {count} candidates from 'resume_rejected' to 'rejected'")
    else:
        print("✅ No candidates with 'resume_rejected' stage found")
    
    conn.close()
    print("✅ Migration complete!")
    
except Exception as e:
    print(f"❌ Migration failed: {e}")
    exit(1)
