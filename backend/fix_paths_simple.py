"""Fix resume file paths in database"""
import os
import sqlite3

# Connect to database
db_path = "talentai.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get all candidates with resume paths
cursor.execute("SELECT id, name, resume_file_path FROM candidates WHERE resume_file_path IS NOT NULL")
candidates = cursor.fetchall()

fixed = 0
missing = 0

for candidate_id, name, old_path in candidates:
    # Extract filename
    filename = os.path.basename(old_path)
    
    # Check if file exists
    full_path = os.path.join("uploads", filename)
    
    if os.path.exists(full_path):
        # Update to just filename
        cursor.execute("UPDATE candidates SET resume_file_path = ? WHERE id = ?", (filename, candidate_id))
        fixed += 1
        print(f"Fixed: {name} - {old_path} -> {filename}")
    else:
        missing += 1
        print(f"Missing: {name} - {filename}")

conn.commit()
conn.close()

print(f"\n{'='*50}")
print(f"Fixed: {fixed} paths")
print(f"Missing: {missing} files")
print(f"{'='*50}")
