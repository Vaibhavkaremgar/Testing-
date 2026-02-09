# Email-Based Status Update Implementation

## Summary
Successfully implemented automatic status updates based on email types sent from N8N workflow.

## Changes Made

### 1. Database Schema (`models.py`)
- Added `display_status` field to `Candidate` model
- This field stores the status to display in Resumes table (separate from pipeline stage)

### 2. Backend Webhook (`webhooks.py`)
Updated `/webhook/log-email` endpoint to:
- Set `stage = INTERVIEW_SCHEDULED` for "Slot Selection Email"
- Set `display_status = "shortlisted"` for "Slot Selection Email"
- Set `stage = REJECTED` for "Rejection Email"  
- Set `display_status = "rejected"` for "Rejection Email"
- Update `stage_updated_at` timestamp

### 3. API Schema (`schemas.py`)
- Added `display_status` field to `CandidateResponse` schema

### 4. Frontend (`Resumes.jsx`)
Updated status column logic:
- Prioritize `display_status` if it exists
- Fall back to `stage` if `display_status` is null
- Shows "Shortlisted" when `display_status = "shortlisted"`
- Shows "Rejected" when `display_status = "rejected"`

### 5. Database Migration (`main.py`)
- Added automatic migration on startup to add `display_status` column
- Migration runs before and after table creation
- Includes verification in startup event

## How It Works

### For "Slot Selection Email":
1. N8N sends email and logs via webhook
2. Backend sets:
   - `stage = "interview_scheduled"` (for pipeline placement)
   - `display_status = "shortlisted"` (for Resumes table display)
3. Result:
   - **Resumes table**: Shows "Shortlisted" status ✓
   - **Pipeline**: Candidate in "Interview Scheduled" column ✓

### For "Rejection Email":
1. N8N sends email and logs via webhook
2. Backend sets:
   - `stage = "rejected"` (for pipeline placement)
   - `display_status = "rejected"` (for Resumes table display)
3. Result:
   - **Resumes table**: Shows "Rejected" status ✓
   - **Pipeline**: Candidate in "Rejected" column ✓

## Testing
1. Start backend: `uvicorn app.main:app --reload`
2. Migration will run automatically on startup
3. Send test webhook from N8N with email type "Slot Selection Email" or "Rejection Email"
4. Verify status in Resumes table and pipeline position

## N8N Webhook Format
```json
{
  "candidate_id": "JOH123",
  "email_type": "Slot Selection Email",
  "status": "sent"
}
```

or

```json
{
  "candidate_id": "JOH123",
  "email_type": "Rejection Email",
  "status": "sent"
}
```
