"""
Test Script for Scoring Fixes
Run: python test_scoring_fixes.py
"""

import sys
sys.path.append('.')

from app.balanced_scoring import evaluate_resume_balanced

# TEST 1: Strong Backend Resume (Should score 70-85)
print("="*80)
print("TEST 1: STRONG BACKEND RESUME")
print("="*80)

strong_backend_resume = {
    'full_text': """
    Rajesh Kumar
    Backend Software Engineer
    Email: rajesh@email.com | Phone: +91-9876543210
    
    Professional Summary
    Backend Software Engineer with 4 years of experience in developing scalable 
    REST APIs, database optimization, and microservices architecture.
    
    Skills
    Python, FastAPI, Spring Boot, PostgreSQL, MySQL, Docker, Git, REST APIs, 
    Microservices, Redis, JWT Authentication
    
    Work Experience
    
    Senior Backend Developer – TechCorp Solutions (2022-Present)
    - Developed REST APIs using FastAPI and PostgreSQL for e-commerce platform
    - Implemented JWT authentication and role-based authorization system
    - Optimized database queries reducing response time by 50%
    - Integrated third-party payment APIs (Razorpay, Stripe)
    - Built microservices architecture using Docker and Kubernetes
    - Collaborated with frontend team for API integration
    
    Backend Developer – StartupXYZ (2020-2022)
    - Built backend services using Spring Boot and MySQL
    - Designed database schema for inventory management system
    - Implemented caching layer using Redis
    - Deployed applications on AWS EC2 and RDS
    
    Education
    B.Tech in Computer Science – IIT Delhi (2020)
    """,
    'years_of_experience': 4
}

job_requirements = {
    'title': 'Backend Software Engineer',
    'required_skills': ['Python', 'FastAPI', 'PostgreSQL', 'Docker', 'REST APIs', 'Git'],
    'experience_min': 2,
    'experience_max': 5,
    'description': 'Backend engineer with 2-5 years experience in API development'
}

result = evaluate_resume_balanced(strong_backend_resume, job_requirements)

print(f"\nTotal Score: {result['total_score']}/100")
print(f"Label: {result['label']}")
print(f"Status: {result['status']}")
print(f"\nComponent Breakdown:")
print(f"  Experience: {result['components']['experience']['score']}/35")
print(f"  Skills: {result['components']['skills']['score']}/30")
print(f"  Projects: {result['components']['projects']['score']}/20")
print(f"  Education: {result['components']['education']['score']}/10")
print(f"  Soft Skills: {result['components']['soft_skills']['score']}/5")

if result['total_score'] >= 70:
    print("\n[PASS] TEST 1 PASSED: Score is 70+ as expected")
else:
    print(f"\n[FAIL] TEST 1 FAILED: Score is {result['total_score']}, expected 70+")

# TEST 2: Weak Resume (Should score <40)
print("\n" + "="*80)
print("TEST 2: WEAK RESUME")
print("="*80)

weak_resume = {
    'full_text': """
    Amit Sharma
    Student
    Email: amit@email.com
    
    Skills
    HTML, CSS, JavaScript, C++
    
    Education
    B.Tech Computer Science – XYZ College (Pursuing, Expected 2025)
    
    Projects
    - Built a simple calculator using HTML/CSS/JavaScript
    - Created a college website as course project
    """,
    'years_of_experience': 0
}

result2 = evaluate_resume_balanced(weak_resume, job_requirements)

print(f"\nTotal Score: {result2['total_score']}/100")
print(f"Label: {result2['label']}")
print(f"Status: {result2['status']}")
print(f"\nComponent Breakdown:")
print(f"  Experience: {result2['components']['experience']['score']}/35")
print(f"  Skills: {result2['components']['skills']['score']}/30")
print(f"  Projects: {result2['components']['projects']['score']}/20")
print(f"  Education: {result2['components']['education']['score']}/10")
print(f"  Soft Skills: {result2['components']['soft_skills']['score']}/5")

if result2['total_score'] < 40:
    print("\n[PASS] TEST 2 PASSED: Score is <40 as expected")
else:
    print(f"\n[FAIL] TEST 2 FAILED: Score is {result2['total_score']}, expected <40")

# TEST 3: Mid-level Resume (Should score 55-70)
print("\n" + "="*80)
print("TEST 3: MID-LEVEL RESUME")
print("="*80)

mid_resume = {
    'full_text': """
    Priya Verma
    Software Developer
    Email: priya@email.com
    
    Skills
    Python, Flask, MySQL, Git
    
    Work Experience
    
    Software Developer – ABC Tech (2022-Present)
    - Developed web applications using Flask and MySQL
    - Worked on database design and optimization
    - Collaborated with team members on feature development
    
    Education
    B.Tech in Computer Science – NIT Trichy (2022)
    """,
    'years_of_experience': 2
}

result3 = evaluate_resume_balanced(mid_resume, job_requirements)

print(f"\nTotal Score: {result3['total_score']}/100")
print(f"Label: {result3['label']}")
print(f"Status: {result3['status']}")
print(f"\nComponent Breakdown:")
print(f"  Experience: {result3['components']['experience']['score']}/35")
print(f"  Skills: {result3['components']['skills']['score']}/30")
print(f"  Projects: {result3['components']['projects']['score']}/20")
print(f"  Education: {result3['components']['education']['score']}/10")
print(f"  Soft Skills: {result3['components']['soft_skills']['score']}/5")

if 50 <= result3['total_score'] <= 70:
    print("\n[PASS] TEST 3 PASSED: Score is 50-70 as expected")
else:
    print(f"\n[FAIL] TEST 3 FAILED: Score is {result3['total_score']}, expected 50-70")

print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print(f"Test 1 (Strong Backend): {result['total_score']}/100 - {'PASS' if result['total_score'] >= 70 else 'FAIL'}")
print(f"Test 2 (Weak Resume): {result2['total_score']}/100 - {'PASS' if result2['total_score'] < 40 else 'FAIL'}")
print(f"Test 3 (Mid-level): {result3['total_score']}/100 - {'PASS' if 50 <= result3['total_score'] <= 70 else 'FAIL'}")
print("="*80)
