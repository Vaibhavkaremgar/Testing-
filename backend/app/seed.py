from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import User, JobDescription, Candidate, Interview, EmailTemplate, Client, CandidateStage, ParsingStatus, UserRole
from app.auth import get_password_hash
from datetime import datetime, timedelta
import random

def seed_database():
    db = SessionLocal()
    
    try:
        # Check if already seeded
        if db.query(User).first():
            return
        
        print("Seeding database with demo data...")
        
        # Create demo users
        users = [
            User(
                email="admin@talentai.com",
                hashed_password=get_password_hash("admin123"),
                full_name="Admin User",
                role=UserRole.ADMIN
            ),
            User(
                email="recruiter@talentai.com",
                hashed_password=get_password_hash("recruiter123"),
                full_name="Sarah Johnson",
                role=UserRole.RECRUITER
            ),
            User(
                email="manager@talentai.com",
                hashed_password=get_password_hash("manager123"),
                full_name="Mike Chen",
                role=UserRole.HIRING_MANAGER
            ),
        ]
        for user in users:
            db.add(user)
        db.commit()
        
        # Create job descriptions
        jobs = [
            JobDescription(
                title="Senior Software Engineer",
                department="Engineering",
                location="San Francisco, CA",
                employment_type="Full-time",
                experience_required="5+ years",
                salary_range="$150,000 - $200,000",
                description="We are looking for a Senior Software Engineer to join our growing team.",
                requirements="Bachelor's degree in CS or related field, 5+ years of experience",
                responsibilities="Design and implement scalable systems, mentor junior developers",
                skills=["Python", "JavaScript", "React", "AWS", "Docker"]
            ),
            JobDescription(
                title="Product Manager",
                department="Product",
                location="New York, NY",
                employment_type="Full-time",
                experience_required="3-5 years",
                salary_range="$120,000 - $160,000",
                description="Looking for an experienced Product Manager to lead product initiatives.",
                requirements="3+ years PM experience, strong analytical skills",
                responsibilities="Define product roadmap, work with engineering and design teams",
                skills=["Product Strategy", "Agile", "Data Analysis", "Roadmapping"]
            ),
            JobDescription(
                title="UX Designer",
                department="Design",
                location="Remote",
                employment_type="Full-time",
                experience_required="2-4 years",
                salary_range="$90,000 - $130,000",
                description="Join our design team to create beautiful user experiences.",
                requirements="Portfolio demonstrating UX expertise, Figma proficiency",
                responsibilities="Create wireframes, prototypes, and final designs",
                skills=["Figma", "User Research", "Prototyping", "Design Systems"]
            ),
            JobDescription(
                title="Data Scientist",
                department="Engineering",
                location="Austin, TX",
                employment_type="Full-time",
                experience_required="3+ years",
                salary_range="$130,000 - $180,000",
                description="Build ML models to power our AI recruitment features.",
                requirements="MS/PhD in quantitative field, Python expertise",
                responsibilities="Develop ML models, analyze data, present findings",
                skills=["Python", "Machine Learning", "SQL", "TensorFlow", "Statistics"]
            ),
        ]
        for job in jobs:
            db.add(job)
        db.commit()
        
        # Create candidates with more data
        candidate_data = [
            ("John Smith", "john.smith@email.com", "Google", "Senior Engineer", 6, "San Francisco"),
            ("Emily Davis", "emily.d@email.com", "Meta", "Product Manager", 4, "New York"),
            ("Michael Brown", "m.brown@email.com", "Amazon", "Software Engineer", 3, "Seattle"),
            ("Sarah Wilson", "sarah.w@email.com", "Netflix", "UX Designer", 5, "Los Angeles"),
            ("David Lee", "david.lee@email.com", "Apple", "Data Scientist", 4, "Austin"),
            ("Jennifer Taylor", "j.taylor@email.com", "Microsoft", "Senior Developer", 7, "Seattle"),
            ("Robert Johnson", "r.johnson@email.com", "Stripe", "Backend Engineer", 5, "San Francisco"),
            ("Lisa Anderson", "l.anderson@email.com", "Airbnb", "Product Designer", 3, "San Francisco"),
            ("James Martinez", "j.martinez@email.com", "Uber", "ML Engineer", 4, "New York"),
            ("Amanda White", "a.white@email.com", "LinkedIn", "Frontend Developer", 2, "San Francisco"),
            ("Christopher Garcia", "c.garcia@email.com", "Twitter", "Full Stack Dev", 6, "San Francisco"),
            ("Michelle Robinson", "m.robinson@email.com", "Salesforce", "QA Engineer", 4, "San Francisco"),
            ("Daniel Clark", "d.clark@email.com", "Adobe", "DevOps Engineer", 5, "San Jose"),
            ("Jessica Lewis", "j.lewis@email.com", "Spotify", "Data Analyst", 3, "New York"),
            ("Andrew Walker", "a.walker@email.com", "Shopify", "Tech Lead", 8, "Remote"),
            # Add 20 more candidates for better testing
            ("Alex Thompson", "alex.t@email.com", "Tesla", "Software Engineer", 3, "Austin"),
            ("Maria Rodriguez", "maria.r@email.com", "Zoom", "Product Manager", 5, "San Jose"),
            ("Kevin Chen", "kevin.c@email.com", "Slack", "Senior Developer", 6, "San Francisco"),
            ("Rachel Green", "rachel.g@email.com", "Dropbox", "UX Designer", 4, "San Francisco"),
            ("Tom Wilson", "tom.w@email.com", "Square", "Data Engineer", 5, "San Francisco"),
            ("Sophie Miller", "sophie.m@email.com", "Twilio", "Frontend Dev", 3, "San Francisco"),
            ("Ryan Davis", "ryan.d@email.com", "Coinbase", "Backend Dev", 4, "San Francisco"),
            ("Emma Johnson", "emma.j@email.com", "Pinterest", "Product Designer", 3, "San Francisco"),
            ("Luke Brown", "luke.b@email.com", "Reddit", "Full Stack Dev", 5, "San Francisco"),
            ("Olivia Taylor", "olivia.t@email.com", "Lyft", "Data Scientist", 4, "San Francisco"),
            ("Nathan Lee", "nathan.l@email.com", "DoorDash", "Mobile Dev", 3, "San Francisco"),
            ("Grace Wang", "grace.w@email.com", "Instacart", "QA Engineer", 2, "San Francisco"),
            ("Jacob Martinez", "jacob.m@email.com", "Robinhood", "DevOps", 4, "Menlo Park"),
            ("Chloe Anderson", "chloe.a@email.com", "Palantir", "Software Engineer", 3, "Palo Alto"),
            ("Ethan Wilson", "ethan.w@email.com", "Snowflake", "Data Engineer", 5, "San Mateo"),
        ]
        
        stages = list(CandidateStage)
        skills_pool = [
            "Python", "JavaScript", "React", "Node.js", "SQL", "AWS", "Docker", 
            "Kubernetes", "Machine Learning", "Data Analysis", "Project Management", 
            "Agile", "Communication", "Leadership", "TypeScript", "Go", "Java"
        ]
        
        candidates = []
        # Distribute candidates across all stages
        stage_distribution = {
            0: CandidateStage.UPLOADED,
            1: CandidateStage.SHORTLISTED, 
            2: CandidateStage.SHORTLISTED,
            3: CandidateStage.SHORTLISTED,
            4: CandidateStage.SHORTLISTED,
            5: CandidateStage.INTERVIEW_SCHEDULED,
            6: CandidateStage.INTERVIEWED,
            7: CandidateStage.INTERVIEWED,
            8: CandidateStage.SELECTED,
            9: CandidateStage.SELECTED,
            10: CandidateStage.REJECTED,
            11: CandidateStage.REJECTED,
        }
        
        for i, (name, email, company, role, exp, location) in enumerate(candidate_data):
            # Use predefined distribution for first 12, then random for rest
            stage = stage_distribution.get(i, random.choice(stages))
            
            candidate = Candidate(
                name=name,
                email=email,
                phone=f"+1-555-{random.randint(100, 999)}-{random.randint(1000, 9999)}",
                current_company=company,
                current_role=role,
                experience_years=exp,
                location=location,
                parsing_status=ParsingStatus.COMPLETED,
                resume_score=round(random.uniform(65, 98), 1),
                skills=random.sample(skills_pool, k=random.randint(4, 8)),
                education=[{"degree": "Bachelor's in Computer Science", "institution": "Tech University", "year": 2020 - exp}],
                work_experience=[{"company": company, "role": role, "duration": f"{exp} years"}],
                stage=stage,
                job_id=random.randint(1, 4),
                created_by=2
            )
            candidates.append(candidate)
            db.add(candidate)
        db.commit()
        
        # Create some interviews
        interview_types = ["screening", "technical", "hr", "final"]
        for i, candidate in enumerate(candidates[:8]):
            if candidate.stage in [CandidateStage.INTERVIEW_SCHEDULED, CandidateStage.INTERVIEWED, CandidateStage.SELECTED]:
                interview = Interview(
                    candidate_id=candidate.id,
                    interview_type=random.choice(interview_types),
                    scheduled_at=datetime.utcnow() + timedelta(days=random.randint(-10, 10)),
                    duration_minutes=60,
                    meeting_link=f"https://meet.talentai.com/interview-{candidate.id}",
                    status="completed" if candidate.stage == CandidateStage.INTERVIEWED else "scheduled",
                    interview_score=round(random.uniform(70, 95), 1) if candidate.stage == CandidateStage.INTERVIEWED else None,
                    technical_score=round(random.uniform(65, 95), 1) if candidate.stage == CandidateStage.INTERVIEWED else None,
                    communication_score=round(random.uniform(70, 95), 1) if candidate.stage == CandidateStage.INTERVIEWED else None,
                    culture_fit_score=round(random.uniform(72, 95), 1) if candidate.stage == CandidateStage.INTERVIEWED else None,
                    ai_summary="Strong candidate with excellent technical skills and communication abilities." if candidate.stage == CandidateStage.INTERVIEWED else None
                )
                db.add(interview)
        db.commit()
        
        # Create email templates
        templates = [
            EmailTemplate(
                name="Interview Invitation",
                subject="Interview Invitation - {{job_title}} at TalentAI",
                body="""Dear {{candidate_name}},

We are pleased to invite you for an interview for the {{job_title}} position at TalentAI.

Interview Details:
- Date: {{interview_date}}
- Time: {{interview_time}}
- Format: {{interview_format}}

Please confirm your availability by replying to this email.

Best regards,
The TalentAI Recruitment Team""",
                template_type="interview_invite",
                variables=["candidate_name", "job_title", "interview_date", "interview_time", "interview_format"]
            ),
            EmailTemplate(
                name="Offer Letter",
                subject="Job Offer - {{job_title}} at TalentAI",
                body="""Dear {{candidate_name}},

We are thrilled to extend an offer for the position of {{job_title}} at TalentAI.

Offer Details:
- Position: {{job_title}}
- Start Date: {{start_date}}
- Compensation: {{salary}}

Please review the attached offer letter and let us know your decision.

Welcome to the team!

Best regards,
The TalentAI Team""",
                template_type="offer",
                variables=["candidate_name", "job_title", "start_date", "salary"]
            ),
            EmailTemplate(
                name="Application Received",
                subject="Application Received - {{job_title}}",
                body="""Dear {{candidate_name}},

Thank you for applying for the {{job_title}} position at TalentAI.

We have received your application and our team is currently reviewing it. We will be in touch soon regarding the next steps.

Best regards,
The TalentAI Recruitment Team""",
                template_type="application_received",
                variables=["candidate_name", "job_title"]
            ),
            EmailTemplate(
                name="Rejection",
                subject="Update on Your Application - TalentAI",
                body="""Dear {{candidate_name}},

Thank you for your interest in the {{job_title}} position at TalentAI and for taking the time to go through our interview process.

After careful consideration, we have decided to move forward with other candidates whose experience more closely matches our current needs.

We encourage you to apply for future openings that match your skills and experience.

Best regards,
The TalentAI Recruitment Team""",
                template_type="rejection",
                variables=["candidate_name", "job_title"]
            ),
        ]
        for template in templates:
            db.add(template)
        db.commit()
        
        # Create clients
        clients_data = [
            Client(
                name="TechCorp Solutions",
                industry="Technology",
                contact_person="John Anderson",
                contact_email="john@techcorp.com",
                contact_phone="+1-555-100-2000",
                total_positions=25,
                positions_filled=18,
                positions_open=7,
                avg_time_to_hire=28.5,
                retention_rate=92.0,
                acceptance_rate=85.0,
                is_active=True
            ),
            Client(
                name="Global Finance Inc",
                industry="Finance",
                contact_person="Sarah Mitchell",
                contact_email="sarah@globalfinance.com",
                contact_phone="+1-555-200-3000",
                total_positions=15,
                positions_filled=12,
                positions_open=3,
                avg_time_to_hire=22.0,
                retention_rate=88.0,
                acceptance_rate=90.0,
                is_active=True
            ),
            Client(
                name="HealthTech Innovations",
                industry="Healthcare",
                contact_person="Dr. Emily Chen",
                contact_email="emily@healthtech.com",
                contact_phone="+1-555-300-4000",
                total_positions=20,
                positions_filled=8,
                positions_open=12,
                avg_time_to_hire=35.0,
                retention_rate=78.0,
                acceptance_rate=72.0,
                is_active=True
            ),
            Client(
                name="RetailMax Group",
                industry="Retail",
                contact_person="Michael Brown",
                contact_email="michael@retailmax.com",
                contact_phone="+1-555-400-5000",
                total_positions=30,
                positions_filled=22,
                positions_open=8,
                avg_time_to_hire=25.0,
                retention_rate=85.0,
                acceptance_rate=80.0,
                is_active=True
            ),
            Client(
                name="EduLearn Platform",
                industry="Education",
                contact_person="Lisa Johnson",
                contact_email="lisa@edulearn.com",
                contact_phone="+1-555-500-6000",
                total_positions=12,
                positions_filled=10,
                positions_open=2,
                avg_time_to_hire=20.0,
                retention_rate=95.0,
                acceptance_rate=88.0,
                is_active=True
            ),
            Client(
                name="AutoDrive Systems",
                industry="Automotive",
                contact_person="Robert Taylor",
                contact_email="robert@autodrive.com",
                contact_phone="+1-555-600-7000",
                total_positions=18,
                positions_filled=6,
                positions_open=12,
                avg_time_to_hire=40.0,
                retention_rate=70.0,
                acceptance_rate=65.0,
                is_active=True
            ),
            Client(
                name="CloudNet Services",
                industry="Cloud Computing",
                contact_person="Amanda White",
                contact_email="amanda@cloudnet.com",
                contact_phone="+1-555-700-8000",
                total_positions=22,
                positions_filled=16,
                positions_open=6,
                avg_time_to_hire=26.0,
                retention_rate=90.0,
                acceptance_rate=82.0,
                is_active=True
            ),
            Client(
                name="MediaStream Co",
                industry="Media & Entertainment",
                contact_person="David Martinez",
                contact_email="david@mediastream.com",
                contact_phone="+1-555-800-9000",
                total_positions=10,
                positions_filled=9,
                positions_open=1,
                avg_time_to_hire=18.0,
                retention_rate=94.0,
                acceptance_rate=92.0,
                is_active=True
            )
        ]
        for client in clients_data:
            db.add(client)
        db.commit()
        
        print("Database seeded successfully!")
        
    except Exception as e:
        print(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
