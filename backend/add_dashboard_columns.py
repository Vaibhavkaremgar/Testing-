"""
Add source and decline_reason columns to candidates table
"""
import sqlite3

def add_new_columns():
    conn = sqlite3.connect('talentai.db')
    cursor = conn.cursor()
    
    try:
        # Add source column
        cursor.execute("""
            ALTER TABLE candidates 
            ADD COLUMN source TEXT
        """)
        print("Added source column")
        
        # Add decline_reason column
        cursor.execute("""
            ALTER TABLE candidates 
            ADD COLUMN decline_reason TEXT
        """)
        print("Added decline_reason column")
        
        # Add offer_status column
        cursor.execute("""
            ALTER TABLE candidates 
            ADD COLUMN offer_status TEXT
        """)
        print("Added offer_status column")
        
        # Add job_status column to job_descriptions
        cursor.execute("""
            ALTER TABLE job_descriptions 
            ADD COLUMN status TEXT DEFAULT 'open'
        """)
        print("Added status column to job_descriptions")
        
        conn.commit()
        print("Migration completed successfully")
        
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    add_new_columns()
