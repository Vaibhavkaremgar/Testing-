import sqlite3

conn = sqlite3.connect('talentai.db')
cursor = conn.cursor()

cursor.execute("SELECT email, full_name, role FROM users")
users = cursor.fetchall()

print(f"Found {len(users)} users:")
for user in users:
    print(f"  - {user[0]} | {user[1]} | {user[2]}")

conn.close()
