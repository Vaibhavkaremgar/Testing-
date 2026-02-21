import sqlite3
from datetime import datetime

conn = sqlite3.connect('talentai.db')
cursor = conn.cursor()

try:
    # Create completed interview for candidate ID 1
    cursor.execute('''
        INSERT INTO interviews (
            candidate_id, interview_type, scheduled_at, duration_minutes,
            status, transcript, ai_summary, interview_score,
            technical_score, communication_score, culture_fit_score,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        1,  # candidate_id
        'technical',
        '2024-02-19 10:00:00',
        60,
        'completed',
        '''Interviewer: Can you explain your experience with Python?
Candidate: I have 5 years of experience with Python, working on web applications using Django and Flask frameworks. I have built RESTful APIs and worked with databases like PostgreSQL and MongoDB.

Interviewer: Tell me about a challenging project you worked on.
Candidate: I developed a real-time data processing system that handled 10,000 requests per second. The main challenge was optimizing database queries and implementing caching strategies using Redis.

Interviewer: How do you handle code reviews?
Candidate: I believe in constructive feedback and always review code for readability, performance, and security. I use tools like SonarQube for static analysis.''',
        'Strong technical candidate with 5 years of Python experience. Demonstrated excellent problem-solving skills and deep understanding of web technologies. Good communication and team collaboration abilities. Recommended for hire.',
        85.0,
        88.0,
        82.0,
        85.0,
        '2024-02-19 10:00:00'
    ))
    
    # Update candidate stage to INTERVIEWED
    cursor.execute('UPDATE candidates SET stage = ? WHERE id = ?', ('INTERVIEWED', 1))
    
    conn.commit()
    print('SUCCESS: Created completed interview')
    print(f'   Interview ID: {cursor.lastrowid}')
    print('   Candidate: Amit Verma')
    print('   Status: completed')
    print('   Scores: Overall=85, Technical=88, Communication=82, Culture Fit=85')
    
except Exception as e:
    print(f'ERROR: {e}')
    conn.rollback()
finally:
    conn.close()
