import sqlite3

conn = sqlite3.connect('talentai.db')
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(job_descriptions)")
columns = cursor.fetchall()

print("Columns in job_descriptions table:")
for col in columns:
    print(f"  {col[1]} ({col[2]})")

conn.close()
