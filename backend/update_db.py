import sqlite3

conn = sqlite3.connect('recruitment.db')
cursor = conn.cursor()
cursor.execute("UPDATE candidates SET stage = 'resume_rejected', display_status = 'resume_rejected' WHERE stage = 'rejected' AND resume_score < 60")
conn.commit()
print(f"Updated {cursor.rowcount} candidates from 'rejected' to 'resume_rejected'")
conn.close()
