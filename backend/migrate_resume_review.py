"""
Migration script to add resume review assignment columns to candidates table
"""
import sqlite3
import os

# Get database path
db_path = os.path.join(os.path.dirname(__file__), 'recruitment.db')

def migrate():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Add assigned_to_user_id column
        cursor.execute("""
            ALTER TABLE candidates 
            ADD COLUMN assigned_to_user_id INTEGER
        """)
        print("✓ Added assigned_to_user_id column")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("✓ assigned_to_user_id column already exists")
        else:
            raise
    
    try:
        # Add review_status column
        cursor.execute("""
            ALTER TABLE candidates 
            ADD COLUMN review_status TEXT DEFAULT 'unassigned'
        """)
        print("✓ Added review_status column")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("✓ review_status column already exists")
        else:
            raise
    
    try:
        # Add reviewed_at column
        cursor.execute("""
            ALTER TABLE candidates 
            ADD COLUMN reviewed_at TIMESTAMP
        """)
        print("✓ Added reviewed_at column")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("✓ reviewed_at column already exists")
        else:
            raise
    
    try:
        # Add reviewed_by_user_id column
        cursor.execute("""
            ALTER TABLE candidates 
            ADD COLUMN reviewed_by_user_id INTEGER
        """)
        print("✓ Added reviewed_by_user_id column")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("✓ reviewed_by_user_id column already exists")
        else:
            raise
    
    conn.commit()
    conn.close()
    print("\n✅ Migration completed successfully!")

if __name__ == "__main__":
    migrate()
