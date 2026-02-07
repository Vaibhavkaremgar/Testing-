#!/usr/bin/env python3
import sqlite3

def check_jobs_and_upload():
    conn = sqlite3.connect('talentai.db')
    cursor = conn.cursor()
    
    print("=== DEBUGGING UPLOAD ISSUE ===\n")
    
    # Check jobs
    cursor.execute("SELECT id, title, is_active FROM job_descriptions")
    jobs = cursor.fetchall()
    print("JOBS IN DATABASE:")
    if jobs:
        for job in jobs:
            print(f"  ID: {job[0]}, Title: {job[1]}, Active: {job[2]}")
    else:
        print("  No jobs found!")
    
    # Check candidates
    cursor.execute("SELECT COUNT(*) FROM candidates")
    candidate_count = cursor.fetchone()[0]
    print(f"\nCANDIDATES: {candidate_count}")
    
    # Check recent uploads
    cursor.execute("SELECT id, name, job_id, created_at FROM candidates ORDER BY created_at DESC LIMIT 5")
    recent = cursor.fetchall()
    print("\nRECENT CANDIDATES:")
    for candidate in recent:
        print(f"  ID: {candidate[0]}, Name: {candidate[1]}, Job ID: {candidate[2]}, Created: {candidate[3]}")
    
    conn.close()

if __name__ == "__main__":
    check_jobs_and_upload()