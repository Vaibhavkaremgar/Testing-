from app.auth import verify_password, get_password_hash
import sqlite3

# Test password hashing
test_password = "admin123"
test_hash = get_password_hash(test_password)
print(f"Test hash: {test_hash}")
print(f"Verify test: {verify_password(test_password, test_hash)}")

# Check database hash
conn = sqlite3.connect('talentai.db')
cursor = conn.cursor()
cursor.execute("SELECT email, hashed_password FROM users WHERE email = 'admin@talentai.com'")
result = cursor.fetchone()

if result:
    email, db_hash = result
    print(f"\nDatabase hash: {db_hash}")
    print(f"Verify against 'admin123': {verify_password('admin123', db_hash)}")
else:
    print("User not found")

conn.close()
