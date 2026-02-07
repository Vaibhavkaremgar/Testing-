"""
Check database contents
"""
import sqlite3

def check_db():
    conn = sqlite3.connect('talentai.db')
    cursor = conn.cursor()
    
    try:
        # Check candidates count
        cursor.execute("SELECT COUNT(*) FROM candidates")
        count = cursor.fetchone()[0]
        print(f"Total candidates: {count}")
        
        # Check stages distribution
        cursor.execute("SELECT stage, COUNT(*) FROM candidates GROUP BY stage")
        stages = cursor.fetchall()
        print("\nCandidates by stage:")
        for stage, cnt in stages:
            print(f"  {stage}: {cnt}")
        
        # Check if candidates have resume_score
        cursor.execute("SELECT COUNT(*) FROM candidates WHERE resume_score IS NOT NULL")
        with_scores = cursor.fetchone()[0]
        print(f"\nCandidates with resume scores: {with_scores}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_db()
