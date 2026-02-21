from app.database import SessionLocal
from app.models import Interview, Candidate, CandidateStage
from datetime import datetime, timedelta
import random

db = SessionLocal()

# Get candidates
candidates = db.query(Candidate).all()
if len(candidates) < 2:
    print("Not enough candidates. Please add candidates first.")
    db.close()
    exit()

print(f"Found {len(candidates)} candidates")

# Update first 2 candidates to INTERVIEWED stage
for i in range(min(2, len(candidates))):
    candidates[i].stage = CandidateStage.INTERVIEWED

completed_interviews = [
    {
        "candidate_id": candidates[0].id,
        "type": "technical",
        "transcript": """Interviewer: Good morning Robert, thanks for joining us today. Let's start with a technical question. Can you explain how you would design a scalable microservices architecture?

Robert: Good morning! I'd start by identifying the core business domains and breaking them into independent services. Each service would have its own database to ensure loose coupling. I'd use API Gateway for routing, implement service discovery with tools like Consul or Eureka, and use message queues like RabbitMQ for async communication.

Interviewer: Excellent. How would you handle authentication across these services?

Robert: I'd implement JWT tokens with a centralized auth service. Each microservice would validate tokens but the auth service would be the single source of truth for user credentials. I'd also implement refresh tokens for better security.

Interviewer: Great answer. Tell me about a challenging bug you've solved recently.

Robert: At Stripe, we had a race condition in our payment processing system. Multiple requests were creating duplicate charges. I implemented distributed locking using Redis and added idempotency keys to ensure each payment was processed exactly once.

Interviewer: How do you ensure code quality in your team?

Robert: I'm a strong advocate for code reviews, automated testing with at least 80% coverage, and CI/CD pipelines. We also do pair programming for complex features and maintain comprehensive documentation.""",
        "summary": "Robert demonstrated exceptional technical depth in system design and architecture. His experience with microservices, distributed systems, and payment processing is impressive. Strong problem-solving skills and excellent communication. Highly recommended for senior backend role.",
        "scores": {"overall": 92, "technical": 95, "communication": 88, "culture": 93}
    },
    {
        "candidate_id": candidates[1].id,
        "type": "screening",
        "transcript": """Interviewer: Hi Lisa, thanks for taking the time to speak with us. Can you tell me about your design process?

Lisa: Hi! My process starts with user research and understanding the problem we're solving. I create user personas, journey maps, and then move to low-fidelity wireframes. After stakeholder feedback, I create high-fidelity prototypes in Figma and conduct usability testing before handoff to developers.

Interviewer: How do you handle disagreements with product managers or developers?

Lisa: I believe in data-driven decisions. If there's a disagreement, I propose A/B testing or user testing to validate assumptions. I also make sure to understand their constraints and find solutions that work for everyone.

Interviewer: What's your experience with design systems?

Lisa: At Airbnb, I contributed to our design system by creating reusable components and documentation. I ensured consistency across products while maintaining flexibility for unique use cases. I'm proficient in Figma's component variants and auto-layout.

Interviewer: Tell me about a project you're most proud of.

Lisa: I redesigned our booking flow which increased conversion by 23%. I conducted extensive user research, identified pain points, simplified the steps from 7 to 4, and added progress indicators. The project took 3 months and involved close collaboration with engineering and product.""",
        "summary": "Lisa shows strong UX fundamentals and excellent collaborative skills. Her data-driven approach and experience with design systems is valuable. The 23% conversion improvement demonstrates real business impact. Good cultural fit with emphasis on user research and cross-functional collaboration.",
        "scores": {"overall": 87, "technical": 85, "communication": 92, "culture": 88}
    }
]

for data in completed_interviews:
    interview = Interview(
        candidate_id=data["candidate_id"],
        interview_type=data["type"],
        scheduled_at=datetime.utcnow() - timedelta(days=random.randint(1, 5)),
        duration_minutes=60,
        meeting_link=f"https://meet.talentai.com/interview-{data['candidate_id']}",
        status="completed",
        video_url=f"https://recordings.talentai.com/video-{data['candidate_id']}.mp4",
        transcript=data["transcript"],
        ai_summary=data["summary"],
        interview_score=data["scores"]["overall"],
        technical_score=data["scores"]["technical"],
        communication_score=data["scores"]["communication"],
        culture_fit_score=data["scores"]["culture"]
    )
    db.add(interview)

db.commit()
print(f"Added {len(completed_interviews)} interviews successfully!")
db.close()
