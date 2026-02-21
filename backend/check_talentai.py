import sqlite3

conn = sqlite3.connect('talentai.db')
cursor = conn.cursor()

try:
    cursor.execute('SELECT COUNT(*) FROM candidates')
    print(f'Total candidates: {cursor.fetchone()[0]}')
    
    cursor.execute('SELECT id, name, email, stage, resume_score FROM candidates LIMIT 10')
    print('\nSample candidates:')
    for row in cursor.fetchall():
        print(f'ID: {row[0]}, Name: {row[1]}, Email: {row[2]}, Stage: {row[3]}, Score: {row[4]}')
except Exception as e:
    print(f'Error: {e}')

conn.close()
