import sqlite3

conn = sqlite3.connect('talentai.db')
cursor = conn.cursor()

# Update "Skills gap" to "Lack of Skills"
cursor.execute("UPDATE candidates SET decline_reason = 'Lack of Skills' WHERE decline_reason = 'Skills gap'")
updated = cursor.rowcount

conn.commit()

print(f"Updated {updated} candidates from 'Skills gap' to 'Lack of Skills'")

# Verify the update
cursor.execute("SELECT decline_reason, COUNT(*) FROM candidates WHERE decline_reason IS NOT NULL GROUP BY decline_reason")
results = cursor.fetchall()
print("\nUpdated Decline Reasons Distribution:")
for reason, count in results:
    print(f"  {reason}: {count}")

conn.close()
