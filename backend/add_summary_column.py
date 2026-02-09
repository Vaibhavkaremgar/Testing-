import sqlite3

# Connect to database
conn = sqlite3.connect('app.db')
cursor = conn.cursor()

try:
    # Add summary column
    cursor.execute('ALTER TABLE candidates ADD COLUMN summary TEXT')
    conn.commit()
    print("✅ Successfully added 'summary' column to candidates table")
except sqlite3.OperationalError as e:
    if 'duplicate column name' in str(e).lower():
        print("ℹ️  Column 'summary' already exists")
    else:
        print(f"❌ Error: {e}")
finally:
    conn.close()
