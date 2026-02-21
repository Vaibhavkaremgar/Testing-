"""
Add interview data to demo candidates in SELECTED and REJECTED stages
"""
import sqlite3

def add_interview_data():
    conn = sqlite3.connect('talentai.db')
    cursor = conn.cursor()
    
    # Get candidates in INTERVIEWED, SELECTED, REJECTED stages
    cursor.execute("SELECT id, name, stage FROM candidates WHERE stage IN ('INTERVIEWED', 'SELECTED', 'REJECTED')")
    candidates = cursor.fetchall()
    
    if not candidates:
        print('No candidates found in INTERVIEWED, SELECTED, or REJECTED stages')
        conn.close()
        return
    
    # Sample interview data
    sample_video_url = "https://example.com/interview-recording.mp4"
    
    sample_transcripts = [
        "Interviewer: Can you tell me about your experience with Python?\nCandidate: I have 4 years of experience working with Python, primarily in backend development using FastAPI and Django frameworks.\n\nInterviewer: What's your approach to debugging complex issues?\nCandidate: I start by reproducing the issue, then use logging and debugging tools to trace the root cause systematically.",
        
        "Interviewer: Describe a challenging project you worked on.\nCandidate: I led the development of a microservices architecture that reduced system latency by 40%. We used Docker and Kubernetes for deployment.\n\nInterviewer: How do you handle tight deadlines?\nCandidate: I prioritize tasks, communicate clearly with stakeholders, and focus on delivering MVP first.",
        
        "Interviewer: What's your experience with databases?\nCandidate: I've worked extensively with PostgreSQL and MongoDB. I'm comfortable with query optimization and database design.\n\nInterviewer: Tell me about a time you mentored junior developers.\nCandidate: I conducted weekly code reviews and pair programming sessions to help them improve their skills."
    ]
    
    sample_summaries = [
        "Strong technical candidate with solid Python and backend development experience. Demonstrated good problem-solving skills and clear communication. Shows leadership potential through mentoring experience.",
        
        "Excellent candidate with proven track record in system architecture and performance optimization. Strong technical skills combined with good project management abilities. Cultural fit is excellent.",
        
        "Good technical foundation but lacks depth in some areas. Communication skills need improvement. May require additional training and mentorship to reach expected performance level."
    ]
    
    for i, (candidate_id, name, stage) in enumerate(candidates):
        # Rotate through sample data
        transcript = sample_transcripts[i % len(sample_transcripts)]
        summary = sample_summaries[i % len(sample_summaries)]
        
        # Generate scores based on stage
        if stage == 'SELECTED':
            tech_score = 75 + (i % 20)
            comm_score = 80 + (i % 15)
            culture_score = 85 + (i % 10)
        elif stage == 'REJECTED':
            tech_score = 40 + (i % 20)
            comm_score = 45 + (i % 15)
            culture_score = 50 + (i % 10)
        else:  # INTERVIEWED
            tech_score = 60 + (i % 20)
            comm_score = 65 + (i % 15)
            culture_score = 70 + (i % 10)
        
        cursor.execute("""
            UPDATE candidates 
            SET interview_video_url = ?,
                interview_transcript = ?,
                interview_ai_summary = ?,
                interview_technical_score = ?,
                interview_communication_score = ?,
                interview_culture_fit_score = ?
            WHERE id = ?
        """, (sample_video_url, transcript, summary, tech_score, comm_score, culture_score, candidate_id))
        
        print(f'Updated {name} ({stage}) - Tech: {tech_score}, Comm: {comm_score}, Culture: {culture_score}')
    
    conn.commit()
    conn.close()
    print(f'\nInterview data added to {len(candidates)} candidates!')

if __name__ == '__main__':
    add_interview_data()
