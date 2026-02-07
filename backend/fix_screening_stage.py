"""
Fix candidates with 'screening' stage by updating them to 'interviewed'
"""
import sqlite3

def fix_screening_stage():
    conn = sqlite3.connect('talentai.db')
    cursor = conn.cursor()
    
    try:
        # Update all candidates with 'screening' stage to 'interviewed'
        cursor.execute("""
            UPDATE candidates 
            SET stage = 'INTERVIEWED' 
            WHERE stage = 'SCREENING'
        """)
        
        rows_affected = cursor.rowcount
        conn.commit()
        print(f"Updated {rows_affected} candidates from 'screening' to 'interviewed' stage")
        
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    fix_screening_stage()
