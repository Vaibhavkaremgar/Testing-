# Stage Duration Tracking - Implementation Summary

## ✅ Implementation Complete

### Backend Changes

#### 1. Database Model (`backend/app/models.py`)
- Added `stage_entered_at` column - updates when candidate moves to new stage
- Added `applied_at` column - set once on upload, never changes
- Both use `server_default=func.now()` for automatic timestamps

#### 2. API Schema (`backend/app/schemas.py`)
- Updated `CandidateResponse` to include:
  - `stage_entered_at: Optional[datetime]`
  - `applied_at: Optional[datetime]`

#### 3. API Routes (`backend/app/routes/candidates.py`)
- **GET /api/candidates**: Returns `stage_entered_at` and `applied_at` in response
- **GET /api/candidates/pipeline/stages**: Includes timestamps in Kanban data
- **PATCH /api/candidates/{id}/stage**: Updates `stage_entered_at` when stage changes

#### 4. Migration Script (`backend/migrate_stage_duration.py`)
- Adds new columns to existing databases
- Sets `stage_entered_at = stage_updated_at` for existing records
- Sets `applied_at = created_at` for existing records
- Handles missing database gracefully

### Frontend Changes

#### 1. Pipeline Component (`frontend/src/pages/Pipeline.jsx`)
- Added `calculateDaysInStage()` - calculates days in current stage
- Added `calculateTotalDays()` - calculates days from application to shortlisted
- Updated `CandidateCard` component with:
  - Timer badge showing "Waiting: X days" (or "few hours" if < 1 day)
  - Total days tracker for Shortlisted stage only
  - No badges for Rejected stage

#### 2. UI Features
- **Timer Badge**: Shows on all cards except Rejected
  - "Waiting: few hours" if < 1 day
  - "Waiting: X day(s)" if >= 1 day
  - Resets when candidate moves to new stage

- **Total Days (Shortlisted only)**:
  - Shows "Total: X day(s) (Applied → Shortlisted)"
  - Helps track time-to-shortlist metric
  - Only visible on Shortlisted stage cards

### Edge Cases Handled
✅ Null `stage_entered_at` - falls back to `applied_at`  
✅ Rejected stage - no duration badges shown  
✅ Same day upload - shows "few hours"  
✅ Existing records - migration sets proper defaults  

### Testing Checklist
- [ ] Upload new resume - verify `applied_at` is set
- [ ] Move to Shortlisted - verify "Waiting: few hours" appears
- [ ] Check Shortlisted cards - verify total days shown
- [ ] Move to Rejected - verify badges disappear
- [ ] Wait 24+ hours - verify "Waiting: 1 day" appears
- [ ] Run migration on existing database - verify no errors

### Deployment Steps
1. **Backend**: Deploy updated models and routes
2. **Migration**: Run `python backend/migrate_stage_duration.py` (for existing databases)
3. **Frontend**: Deploy updated Pipeline.jsx
4. **Verify**: Check Kanban board shows duration badges

### Files Modified
- `backend/app/models.py` - Added timestamp columns
- `backend/app/schemas.py` - Updated response schema
- `backend/app/routes/candidates.py` - Updated API endpoints
- `frontend/src/pages/Pipeline.jsx` - Added duration tracking UI

### Files Created
- `backend/migrate_stage_duration.py` - Database migration script
- `STAGE_DURATION_MIGRATION.md` - Migration guide
- `STAGE_DURATION_SUMMARY.md` - This file

## 🚀 Ready to Deploy!
