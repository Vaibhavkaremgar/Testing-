import sqlite3

conn = sqlite3.connect('talentai.db')
cursor = conn.cursor()

# Check if decline_reason column exists
cursor.execute("PRAGMA table_info(candidates)")
columns = cursor.fetchall()
print("Columns in candidates table:")
for col in columns:
    print(f"  {col[1]} ({col[2]})")

# Check decline reasons
cursor.execute("SELECT name, decline_reason FROM candidates WHERE decline_reason IS NOT NULL")
results = cursor.fetchall()
print(f"\nCandidates with decline reasons: {len(results)}")
for name, reason in results:
    print(f"  {name}: {reason}")

# Count by decline reason
cursor.execute("SELECT decline_reason, COUNT(*) FROM candidates WHERE decline_reason IS NOT NULL GROUP BY decline_reason")
results = cursor.fetchall()
print("\nDecline Reasons Distribution:")
for reason, count in results:
    print(f"  {reason}: {count}")

conn.close()
