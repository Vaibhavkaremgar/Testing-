import sqlite3
import os

def clear_all_tables():
    """Delete all records from all tables except users"""
    db_path = "recruitment.db"
    
    if not os.path.exists(db_path):
        print("Database doesn't exist")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all table names
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    
    print(f"Found tables: {tables}")
    
    # Delete from all tables except users
    for table in tables:
        if table == 'users':
            print(f"Skipping users table")
            continue
        
        try:
            cursor.execute(f"DELETE FROM {table}")
            count = cursor.rowcount
            print(f"Deleted {count} records from {table}")
        except Exception as e:
            print(f"Error deleting from {table}: {e}")
    
    conn.commit()
    conn.close()
    print("\n✅ All records deleted (users preserved)")

if __name__ == "__main__":
    clear_all_tables()
