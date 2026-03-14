"""
Migration script to add created_by_user_id column to clients table
"""
import sqlite3
import sys

def migrate():
    try:
        # Connect to database
        conn = sqlite3.connect('recruitment.db')
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(clients)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'created_by_user_id' in columns:
            print("✅ Column 'created_by_user_id' already exists in clients table")
            conn.close()
            return
        
        # Add the new column
        print("Adding 'created_by_user_id' column to clients table...")
        cursor.execute("""
            ALTER TABLE clients 
            ADD COLUMN created_by_user_id INTEGER 
            REFERENCES users(id)
        """)
        
        conn.commit()
        print("✅ Successfully added 'created_by_user_id' column to clients table")
        
        # Get the first admin user ID
        cursor.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1")
        admin_user = cursor.fetchone()
        
        if admin_user:
            admin_id = admin_user[0]
            # Update existing clients to be owned by admin
            cursor.execute("""
                UPDATE clients 
                SET created_by_user_id = ? 
                WHERE created_by_user_id IS NULL
            """, (admin_id,))
            conn.commit()
            print(f"✅ Assigned existing clients to admin user (ID: {admin_id})")
        else:
            print("⚠️  No admin user found. Existing clients will have NULL created_by_user_id")
        
        conn.close()
        print("✅ Migration completed successfully!")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    migrate()
