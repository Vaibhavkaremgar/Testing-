"""
Add test candidates for December 2025 and January 2026
"""
import sqlite3
from datetime import datetime
import random

def add_test_candidates():
    conn = sqlite3.connect('talentai.db')
    cursor = conn.cursor()
    
    try:
        # December 2025 candidates
        dec_2025_candidates = [
            ("Alice Johnson", "alice.j@email.com", "+1-555-101-2001", "Microsoft", "Senior Engineer", 5, "Seattle", "SHORTLISTED", 85.5),
            ("Bob Smith", "bob.s@email.com", "+1-555-102-2002", "Amazon", "Product Manager", 4, "Seattle", "INTERVIEWED", 88.2),
            ("Carol White", "carol.w@email.com", "+1-555-103-2003", "Google", "Data Scientist", 6, "San Francisco", "SELECTED", 92.1),
            ("David Brown", "david.b@email.com", "+1-555-104-2004", "Apple", "UX Designer", 3, "Cupertino", "REJECTED", 65.3),
            ("Emma Davis", "emma.d@email.com", "+1-555-105-2005", "Meta", "Software Engineer", 4, "Menlo Park", "SHORTLISTED", 87.8),
            ("Frank Miller", "frank.m@email.com", "+1-555-106-2006", "Netflix", "DevOps Engineer", 5, "Los Gatos", "INTERVIEWED", 89.4),
            ("Grace Lee", "grace.l@email.com", "+1-555-107-2007", "Tesla", "ML Engineer", 4, "Palo Alto", "UPLOADED", 78.9),
            ("Henry Wilson", "henry.w@email.com", "+1-555-108-2008", "Uber", "Backend Dev", 3, "San Francisco", "INTERVIEW_SCHEDULED", 82.6),
        ]
        
        # January 2026 candidates
        jan_2026_candidates = [
            ("Ivy Martinez", "ivy.m@email.com", "+1-555-201-3001", "Salesforce", "Full Stack Dev", 5, "San Francisco", "SHORTLISTED", 86.7),
            ("Jack Anderson", "jack.a@email.com", "+1-555-202-3002", "Adobe", "Frontend Dev", 4, "San Jose", "INTERVIEWED", 84.3),
            ("Kate Taylor", "kate.t@email.com", "+1-555-203-3003", "LinkedIn", "Data Engineer", 6, "Sunnyvale", "SELECTED", 91.5),
            ("Leo Thomas", "leo.t@email.com", "+1-555-204-3004", "Twitter", "Product Designer", 3, "San Francisco", "REJECTED", 68.2),
            ("Mia Jackson", "mia.j@email.com", "+1-555-205-3005", "Airbnb", "Senior Developer", 7, "San Francisco", "SHORTLISTED", 90.1),
            ("Noah Harris", "noah.h@email.com", "+1-555-206-3006", "Spotify", "QA Engineer", 4, "New York", "INTERVIEWED", 83.8),
            ("Olivia Clark", "olivia.c@email.com", "+1-555-207-3007", "Dropbox", "Cloud Engineer", 5, "San Francisco", "UPLOADED", 79.5),
            ("Paul Lewis", "paul.l@email.com", "+1-555-208-3008", "Slack", "Tech Lead", 8, "San Francisco", "INTERVIEW_SCHEDULED", 88.9),
            ("Quinn Walker", "quinn.w@email.com", "+1-555-209-3009", "Zoom", "Mobile Dev", 3, "San Jose", "SELECTED", 85.4),
            ("Ruby Hall", "ruby.h@email.com", "+1-555-210-3010", "Square", "Security Engineer", 6, "San Francisco", "SHORTLISTED", 87.2),
        ]
        
        skills_pool = ["Python", "JavaScript", "React", "Node.js", "SQL", "AWS", "Docker", "Kubernetes", "Machine Learning", "Data Analysis"]
        
        # Insert December 2025 candidates
        for name, email, phone, company, role, exp, location, stage, score in dec_2025_candidates:
            created_at = f"2025-12-{random.randint(1, 28):02d} {random.randint(9, 17):02d}:{random.randint(0, 59):02d}:00"
            skills = str(random.sample(skills_pool, k=random.randint(4, 7))).replace("'", '"')
            
            cursor.execute("""
                INSERT INTO candidates (
                    name, email, phone, current_company, current_role, experience_years, 
                    location, stage, resume_score, skills, parsing_status, 
                    job_id, created_by, created_at, stage_updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'COMPLETED', 1, 2, ?, ?)
            """, (name, email, phone, company, role, exp, location, stage, score, skills, created_at, created_at))
        
        # Insert January 2026 candidates
        for name, email, phone, company, role, exp, location, stage, score in jan_2026_candidates:
            created_at = f"2026-01-{random.randint(1, 31):02d} {random.randint(9, 17):02d}:{random.randint(0, 59):02d}:00"
            skills = str(random.sample(skills_pool, k=random.randint(4, 7))).replace("'", '"')
            
            cursor.execute("""
                INSERT INTO candidates (
                    name, email, phone, current_company, current_role, experience_years, 
                    location, stage, resume_score, skills, parsing_status, 
                    job_id, created_by, created_at, stage_updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'COMPLETED', 1, 2, ?, ?)
            """, (name, email, phone, company, role, exp, location, stage, score, skills, created_at, created_at))
        
        conn.commit()
        print(f"Added {len(dec_2025_candidates)} candidates for December 2025")
        print(f"Added {len(jan_2026_candidates)} candidates for January 2026")
        print(f"Total: {len(dec_2025_candidates) + len(jan_2026_candidates)} test candidates added")
        
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    add_test_candidates()
