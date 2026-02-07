"""
Update existing candidates with source and decline_reason data
"""
import sqlite3
import random

def update_candidate_data():
    conn = sqlite3.connect('talentai.db')
    cursor = conn.cursor()
    
    try:
        sources = ['LinkedIn', 'Referral', 'Job Board', 'Career Site', 'Indeed', 'Glassdoor']
        decline_reasons = [
            'Salary expectations not met',
            'Accepted another offer',
            'Location mismatch',
            'Lack of Skills',
            'Cultural fit concerns',
            'Failed technical assessment'
        ]
        
        # Get all candidates
        cursor.execute("SELECT id, stage FROM candidates")
        candidates = cursor.fetchall()
        
        for candidate_id, stage in candidates:
            # Assign random source
            source = random.choice(sources)
            cursor.execute("UPDATE candidates SET source = ? WHERE id = ?", (source, candidate_id))
            
            # If rejected, assign decline reason
            if stage == 'REJECTED':
                reason = random.choice(decline_reasons)
                cursor.execute("UPDATE candidates SET decline_reason = ? WHERE id = ?", (reason, candidate_id))
            
            # If selected, mark offer as accepted
            if stage == 'SELECTED':
                cursor.execute("UPDATE candidates SET offer_status = 'accepted' WHERE id = ?", (candidate_id,))
        
        # Update some candidates with offer_made status
        cursor.execute("""
            UPDATE candidates 
            SET offer_status = 'made' 
            WHERE stage IN ('INTERVIEWED', 'SELECTED') 
            AND id % 3 = 0
        """)
        
        conn.commit()
        print(f"Updated {len(candidates)} candidates with source and decline_reason data")
        
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    update_candidate_data()
