# Asynchronous Interview System

## Overview
A manual, non-AI question generation system for fair and consistent candidate evaluation.

## Key Design Principles
✅ **Manual Question Entry** - Recruiters enter all questions  
✅ **No AI Generation** - Questions are never auto-generated  
✅ **Consistent Evaluation** - Same questions for all candidates  
✅ **Auditability** - Full control and transparency  

---

## Database Schema

### JobDescription Model
```python
interview_questions: JSON  # Array of question objects
```

**Question Object Structure:**
```json
{
  "id": 1,
  "text": "Explain your approach to system design",
  "type": "text",  // text, video, coding, mcq
  "category": "technical",  // technical, behavioral, system_design
  "difficulty": "medium",  // easy, medium, hard
  "time_limit_seconds": 600,
  "points": 10
}
```

### Interview Model (Extended)
```python
is_async: Boolean
async_link: String  # Unique candidate link
async_token: String  # Access token
async_expires_at: DateTime
async_started_at: DateTime
async_completed_at: DateTime
async_answers: JSON  # Candidate responses
```

**Answer Object Structure:**
```json
{
  "question_id": 1,
  "answer": "My approach involves...",
  "time_taken_seconds": 450
}
```

---

## API Endpoints

### 1. Create Job with Questions
**POST** `/api/jobs`

```json
{
  "title": "Senior Backend Engineer",
  "interview_questions": [
    {
      "id": 1,
      "text": "Describe your experience with microservices",
      "type": "text",
      "category": "technical",
      "difficulty": "medium",
      "time_limit_seconds": 600
    },
    {
      "id": 2,
      "text": "Record a video explaining your leadership style",
      "type": "video",
      "category": "behavioral",
      "difficulty": "easy",
      "time_limit_seconds": 300
    }
  ]
}
```

### 2. Get Job Questions
**GET** `/api/jobs/{job_id}`

Returns job with `interview_questions` array.

### 3. Create Async Interview
**POST** `/api/async-interviews/create`

```json
{
  "candidate_id": 123,
  "interview_type": "async",
  "duration_minutes": 60,
  "expires_in_days": 7
}
```

**Response:**
```json
{
  "interview_id": 456,
  "async_link": "http://localhost:5173/async-interview/abc123xyz",
  "expires_at": "2024-01-15T10:00:00Z",
  "candidate_name": "John Doe",
  "candidate_email": "john@example.com"
}
```

### 4. Candidate Access (No Auth)
**GET** `/api/async-interviews/token/{token}`

Returns:
```json
{
  "interview_id": 456,
  "candidate_name": "John Doe",
  "job_title": "Senior Backend Engineer",
  "questions": [...],
  "duration_minutes": 60,
  "started_at": null,
  "status": "scheduled"
}
```

### 5. Submit Answers (No Auth)
**POST** `/api/async-interviews/token/{token}/submit`

```json
{
  "answers": [
    {
      "question_id": 1,
      "answer": "I have 5 years of experience...",
      "time_taken_seconds": 450
    }
  ]
}
```

### 6. Recruiter Review
**GET** `/api/async-interviews/{interview_id}/answers`

Returns questions with candidate answers for evaluation.

---

## Workflow

### Recruiter Flow
1. Create job description
2. Manually enter interview questions (no AI)
3. Save job with questions to database
4. Shortlist candidates
5. Create async interview → generates unique link
6. Send link to candidate via email
7. Review submitted answers
8. (Optional) Use AI only for answer evaluation

### Candidate Flow
1. Receive unique interview link via email
2. Click link (no login required)
3. View questions (fetched from database)
4. Answer questions at own pace
5. Submit answers
6. Confirmation message

---

## Frontend Components Needed

### 1. Job Creation Form
```jsx
// Add question builder UI
<QuestionBuilder>
  <Input placeholder="Question text" />
  <Select options={["text", "video", "coding", "mcq"]} />
  <Select options={["technical", "behavioral"]} />
  <Input type="number" placeholder="Time limit (seconds)" />
  <Button>Add Question</Button>
</QuestionBuilder>
```

### 2. Async Interview Page (Public)
```jsx
// Route: /async-interview/:token
<AsyncInterviewPage>
  <Timer duration={60} />
  <QuestionList questions={questions} />
  <AnswerForm onSubmit={submitAnswers} />
</AsyncInterviewPage>
```

### 3. Answer Review Page (Recruiter)
```jsx
<AnswerReview>
  <QuestionAnswerPair 
    question={q} 
    answer={a} 
    timeTaken={t} 
  />
  <ScoreInput /> {/* Optional AI scoring */}
</AnswerReview>
```

---

## Migration

Run migration script:
```bash
cd backend
python migrate_async_interviews.py
```

Or restart backend (auto-migration on startup).

---

## Security

- Unique token per interview (32-byte URL-safe)
- Token expiration (default 7 days)
- No authentication required for candidate access
- Recruiter endpoints require JWT auth
- One-time submission (status check prevents re-submission)

---

## Question Types

### Text
- Free-form text response
- Time limit enforced on frontend
- Stored as plain text

### Video
- Record video response
- Upload to storage (S3/local)
- Store video URL in answer

### Coding
- Code editor interface
- Language selection
- Test case validation (optional)

### MCQ
- Multiple choice options
- Single or multiple selection
- Auto-scoring

---

## Example: Complete Flow

```python
# 1. Recruiter creates job
POST /api/jobs
{
  "title": "Python Developer",
  "interview_questions": [
    {"id": 1, "text": "Explain decorators", "type": "text"}
  ]
}

# 2. Recruiter creates async interview
POST /api/async-interviews/create
{"candidate_id": 5, "expires_in_days": 7}
→ Returns: async_link

# 3. Candidate accesses
GET /api/async-interviews/token/abc123
→ Returns: questions from job

# 4. Candidate submits
POST /api/async-interviews/token/abc123/submit
{"answers": [{"question_id": 1, "answer": "..."}]}

# 5. Recruiter reviews
GET /api/async-interviews/456/answers
→ Returns: questions + answers
```

---

## Benefits

✅ **Fair** - Same questions for all candidates  
✅ **Stable** - No AI variability in questions  
✅ **Auditable** - Full question history  
✅ **Flexible** - Candidates answer on their schedule  
✅ **Scalable** - No interviewer time required  
✅ **Consistent** - Standardized evaluation criteria  

---

## Optional AI Usage

AI can be used ONLY for:
- Answer evaluation/scoring
- Sentiment analysis
- Keyword extraction
- Quality assessment

AI must NEVER be used for:
- Question generation
- Question modification
- Interview structure
