"""
Migration script to add interview fields to candidates table
"""
import sqlite3

def migrate():
    conn = sqlite3.connect('talentai.db')
    cursor = conn.cursor()
    
    # Add new columns
    columns = [
        ('interview_video_url', 'TEXT'),
        ('interview_transcript', 'TEXT'),
        ('interview_ai_summary', 'TEXT'),
        ('interview_technical_score', 'REAL'),
        ('interview_communication_score', 'REAL'),
        ('interview_culture_fit_score', 'REAL')
    ]
    
    for col_name, col_type in columns:
        try:
            cursor.execute(f'ALTER TABLE candidates ADD COLUMN {col_name} {col_type}')
            print(f'Added column: {col_name}')
        except sqlite3.OperationalError as e:
            if 'duplicate column name' in str(e):
                print(f'Column already exists: {col_name}')
            else:
                raise
    
    conn.commit()
    conn.close()
    print('Migration completed!')

if __name__ == '__main__':
    migrate()
