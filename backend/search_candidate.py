#!/usr/bin/env python3
import sqlite3
import sys

def search_candidate(search_term):
    conn = sqlite3.connect('talentai.db')
    cursor = conn.cursor()
    
    # Search by name (case insensitive)
    cursor.execute("""
        SELECT id, name, email, phone, current_company, current_role, stage, resume_score, created_at 
        FROM candidates 
        WHERE name LIKE ? OR name LIKE ?
    """, (f"%{search_term}%", f"%{search_term.title()}%"))
    
    results = cursor.fetchall()
    
    if results:
        print(f"Found {len(results)} candidate(s) matching '{search_term}':")
        print("-" * 80)
        for result in results:
            print(f"ID: {result[0]}")
            print(f"Name: {result[1]}")
            print(f"Email: {result[2]}")
            print(f"Phone: {result[3]}")
            print(f"Company: {result[4]}")
            print(f"Role: {result[5]}")
            print(f"Stage: {result[6]}")
            print(f"Score: {result[7]}")
            print(f"Created: {result[8]}")
            print("-" * 80)
    else:
        print(f"No candidates found matching '{search_term}'")
    
    conn.close()

if __name__ == "__main__":
    search_term = sys.argv[1] if len(sys.argv) > 1 else "Bhimaraju"
    search_candidate(search_term)