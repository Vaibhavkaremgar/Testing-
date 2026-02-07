"""
Test script to verify LLM integration for resume analysis
Run: python test_llm.py
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.routes.candidates import evaluate_candidate_contextually

# Test data
resume_text = """
John Doe
Software Engineer
john.doe@email.com | (555) 123-4567

EXPERIENCE
Senior Software Engineer at Tech Corp (2020-2024)
- Led development of microservices architecture using Python and FastAPI
- Managed team of 5 developers
- Implemented CI/CD pipelines with Docker and Kubernetes
- Built RESTful APIs serving 1M+ requests/day

Software Engineer at StartupXYZ (2018-2020)
- Developed full-stack web applications using React and Node.js
- Worked with PostgreSQL and MongoDB databases
- Collaborated with cross-functional teams

SKILLS
Python, JavaScript, React, FastAPI, Docker, Kubernetes, PostgreSQL, MongoDB, AWS, Git

EDUCATION
Bachelor of Science in Computer Science
Tech University, 2018
"""

job_description = """
We are looking for a Senior Backend Engineer to join our team.

Requirements:
- 5+ years of experience in backend development
- Strong proficiency in Python and FastAPI
- Experience with microservices architecture
- Knowledge of Docker and Kubernetes
- Database experience (PostgreSQL preferred)
- Experience with cloud platforms (AWS/GCP)
- Strong problem-solving skills
- Team leadership experience

Responsibilities:
- Design and implement scalable backend services
- Lead technical discussions and code reviews
- Mentor junior developers
- Optimize application performance
"""

print("=" * 60)
print("TESTING LLM RESUME ANALYSIS")
print("=" * 60)

try:
    result = evaluate_candidate_contextually(
        resume_text=resume_text,
        job_title="Senior Backend Engineer",
        job_description=job_description,
        job_requirements="5+ years Python, FastAPI, Docker, Kubernetes",
        candidate_skills=["Python", "FastAPI", "Docker", "Kubernetes", "PostgreSQL"],
        experience_text="6 years",
        projects=[]
    )
    
    print("\n✅ ANALYSIS SUCCESSFUL!\n")
    print(f"Match Score: {result['match_score']}/100")
    print(f"Match Label: {result['match_label']}")
    print(f"Status: {result['status']}")
    print(f"\nCandidate Summary:\n{result['candidate_summary']}")
    print(f"\nKey Strengths:")
    for strength in result['key_strengths']:
        print(f"  ✓ {strength}")
    print(f"\nSkill Gaps:")
    for gap in result['skill_gaps']:
        print(f"  ⚠ {gap}")
    print(f"\nAI Analysis:\n{result['ai_analysis']}")
    
    print("\n" + "=" * 60)
    if "keyword" in result['ai_analysis'].lower():
        print("⚠️  WARNING: Still using keyword-based fallback")
        print("💡 Add GROQ_API_KEY to .env for TRUE AI analysis")
    else:
        print("🎉 TRUE AI ANALYSIS WORKING!")
    print("=" * 60)
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    print("\n💡 Make sure to:")
    print("   1. Add GROQ_API_KEY to backend/.env")
    print("   2. Install: pip install requests")
    print("   3. Get free key: https://console.groq.com/keys")
