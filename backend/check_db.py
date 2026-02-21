import sqlite3
import os

db_path = "recruitment.db"

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check candidates
    cursor.execute("SELECT COUNT(*) FROM candidates")
    candidates_count = cursor.fetchone()[0]
    
    # Check interviews
    cursor.execute("SELECT COUNT(*) FROM interviews")
    interviews_count = cursor.fetchone()[0]
    
    # Check jobs
    cursor.execute("SELECT COUNT(*) FROM job_descriptions")
    jobs_count = cursor.fetchone()[0]
    
    # Check users
    cursor.execute("SELECT COUNT(*) FROM users")
    users_count = cursor.fetchone()[0]
    
    print("=" * 50)
    print("DATABASE STATUS")
    print("=" * 50)
    print(f"Candidates: {candidates_count}")
    print(f"Interviews: {interviews_count}")
    print(f"Jobs: {jobs_count}")
    print(f"Users: {users_count}")
    print("=" * 50)
    
    if candidates_count > 0:
        print("\n⚠️  CANDIDATES EXIST IN DATABASE!")
        print("\nTo fix:")
        print("1. Stop backend (Ctrl+C)")
        print("2. Run: python clear_data.py")
        print("3. Restart backend")
        print("4. Clear browser cache:")
        print("   - Chrome: Ctrl+Shift+Delete > Clear data")
        print("   - Or open DevTools (F12) > Network tab > Disable cache")
        print("5. Hard refresh: Ctrl+Shift+R")
    else:
        print("\n✅ Database is clean (no candidates)")
        print("\nIf dashboard still shows values:")
        print("1. Open browser DevTools (F12)")
        print("2. Go to Application tab > Storage > Clear site data")
        print("3. Hard refresh: Ctrl+Shift+R")
    
    conn.close()
else:
    print("❌ Database file doesn't exist")
    print("\nRestart backend to create it:")
    print("uvicorn app.main:app --reload --port 8000")
