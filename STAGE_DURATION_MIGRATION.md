# Stage Duration Tracking - Migration Guide

## Overview
This feature adds duration tracking to the Candidate Pipeline Kanban board, showing:
- **Waiting time**: Days in current stage
- **Total time**: Days from application to shortlisted (shown only on Shortlisted cards)

## Database Changes
Two new timestamp columns added to `candidates` table:
- `stage_entered_at`: Updated every time candidate moves to a new stage
- `applied_at`: Set once when candidate is first uploaded, never changes

## Migration Steps

### For Existing Databases:

1. **Stop the backend** if it's running

2. **Run the migration script**:
   ```bash
   cd backend
   python migrate_stage_duration.py
   ```

3. **Start the backend**:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

### For New Installations:
No migration needed! The new columns will be created automatically when the database is initialized.

## Features

### Timer Badge on Each Card
- Shows "Waiting: X days" for all stages except Rejected
- Shows "Waiting: few hours" if less than 1 day
- Resets when candidate moves to new stage

### Total Days Tracker (Shortlisted Only)
- Shows "Total: X days (Applied → Shortlisted)" 
- Calculates time from application to reaching shortlisted stage
- Helps recruiters track time-to-shortlist metric

### Edge Cases Handled
- If `stage_entered_at` is null, falls back to `applied_at`
- Rejected stage cards show no duration badges
- Handles timezone conversions properly

## API Changes

### Updated Endpoints:
- `GET /api/candidates` - Now includes `stage_entered_at` and `applied_at`
- `GET /api/candidates/pipeline/stages` - Includes timestamps for Kanban cards
- `PATCH /api/candidates/{id}/stage` - Updates `stage_entered_at` on stage change

### Response Schema:
```json
{
  "id": 1,
  "name": "John Doe",
  "stage": "SHORTLISTED",
  "stage_entered_at": "2024-01-15T10:30:00Z",
  "applied_at": "2024-01-10T08:00:00Z"
}
```

## Frontend Changes

### Pipeline.jsx Updates:
- Added duration calculation functions
- Updated CandidateCard component with timer badges
- Conditional rendering for Shortlisted stage total days

## Testing

1. Upload a new resume - should have `applied_at` set
2. Move candidate to Shortlisted - should show "Waiting: few hours"
3. Wait 24+ hours - should show "Waiting: 1 day"
4. Check Shortlisted cards - should show total days from application
5. Move to Rejected - duration badges should disappear

## Deployment

After deploying, the migration will run automatically on first backend start if using the updated models. For production databases, run the migration script manually before deploying.
