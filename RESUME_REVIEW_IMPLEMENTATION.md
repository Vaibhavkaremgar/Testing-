# Resume Assignment and Review Workflow - Implementation Summary

## Overview
Implemented a resume assignment and review system where admins can assign resumes to users for review, and users can send interview invitations or reject candidates.

## Database Changes

### New Columns Added to `candidates` Table:
- `assigned_to_user_id` (INTEGER, nullable) - Foreign key to users table
- `review_status` (TEXT) - Enum: unassigned, pending, interview_invited, rejected
- `reviewed_at` (TIMESTAMP, nullable) - When the review was completed
- `reviewed_by_user_id` (INTEGER, nullable) - Foreign key to users table

### New Enum Added to `models.py`:
```python
class ReviewStatus(str, enum.Enum):
    UNASSIGNED = "unassigned"
    PENDING = "pending"
    INTERVIEW_INVITED = "interview_invited"
    REJECTED = "rejected"
```

## Backend API Endpoints

### 1. Assign Candidate (Admin Only)
**POST** `/api/candidates/{candidate_id}/assign`
- Body: `{ "assigned_to_user_id": <user_id> }`
- Sets review_status to "pending"
- Only admins can assign

### 2. Review Candidate
**POST** `/api/candidates/{candidate_id}/review`
- Body: `{ "action": "interview" | "reject" }`
- Only assigned user can review
- Actions:
  - `interview`: Sets review_status to "interview_invited", moves to INTERVIEW_SCHEDULED stage
  - `reject`: Sets review_status to "rejected", moves to REJECTED stage

### 3. Get My Assigned Candidates
**GET** `/api/candidates/assigned/me`
- Returns list of candidates assigned to current user
- Includes review_status and timestamps

## Frontend Changes

### 1. Sidebar Navigation
- **Admin**: Sees all 10 tabs including Resumes
- **Regular Users**: Now see Resumes tab (8 tabs total)

### 2. API Client Methods (api.js)
```javascript
assignCandidate(id, userId)  // Assign candidate to user
reviewCandidate(id, action)  // Review with "interview" or "reject"
getMyAssignedCandidates()    // Get assigned candidates
```

### 3. Resumes Page Behavior

#### Admin View:
- Upload section visible
- Can assign candidates to users via dropdown
- Full candidate management (edit, delete)
- See all candidates

#### User View:
- No upload section
- See only assigned candidates
- Review buttons: "Send Interview" and "Reject"
- Read-only view of candidate details

## Migration Script

Run this to add new columns:
```bash
cd backend
python migrate_resume_review.py
```

## Workflow

1. **Admin uploads resumes** → Candidates created with review_status = "unassigned"
2. **Admin assigns to user** → review_status = "pending", assigned_to_user_id set
3. **User reviews resume** → Clicks "Send Interview" or "Reject"
4. **System updates**:
   - review_status = "interview_invited" or "rejected"
   - reviewed_at = current timestamp
   - reviewed_by_user_id = current user
   - stage = INTERVIEW_SCHEDULED or REJECTED

## Next Steps for Full Implementation

### Frontend Modifications Needed in Resumes.jsx:

1. **Add user context check**:
```javascript
import { useAuth } from '@/context/AuthContext'
const { user } = useAuth()
const isAdmin = user?.role === 'admin'
```

2. **Conditional rendering for upload section**:
```javascript
{isAdmin && (
  <Card>
    <CardHeader>Upload Resumes</CardHeader>
    {/* Upload section */}
  </Card>
)}
```

3. **Add assignment dropdown in table (admin only)**:
```javascript
{isAdmin && (
  <select onChange={(e) => handleAssign(candidate.id, e.target.value)}>
    <option value="">Assign to...</option>
    {users.map(u => <option key={u.id} value={u.id}>{u.full_name}</option>)}
  </select>
)}
```

4. **Add review buttons (user view)**:
```javascript
{!isAdmin && candidate.assigned_to_user_id === user.id && (
  <>
    <Button onClick={() => handleReview(candidate.id, 'interview')}>
      Send Interview
    </Button>
    <Button onClick={() => handleReview(candidate.id, 'reject')}>
      Reject
    </Button>
  </>
)}
```

5. **Fetch logic**:
```javascript
const fetchCandidates = async () => {
  if (isAdmin) {
    // Fetch all candidates
    const data = await api.getCandidates()
  } else {
    // Fetch only assigned candidates
    const data = await api.getMyAssignedCandidates()
  }
  setCandidates(data)
}
```

## Files Modified

### Backend:
- `backend/app/models.py` - Added ReviewStatus enum and new columns
- `backend/app/schemas.py` - Added CandidateAssign and CandidateReview schemas
- `backend/app/routes/candidates.py` - Added 3 new endpoints
- `backend/migrate_resume_review.py` - Migration script (NEW)

### Frontend:
- `frontend/src/components/layout/Sidebar.jsx` - Added Resumes tab for users
- `frontend/src/lib/api.js` - Added 3 new API methods
- `frontend/src/pages/Resumes.jsx` - Needs role-based UI (see Next Steps)

## Testing Checklist

- [ ] Run migration script locally
- [ ] Test admin can assign candidates
- [ ] Test user sees only assigned candidates
- [ ] Test user can send interview invitation
- [ ] Test user can reject candidate
- [ ] Test stage updates correctly
- [ ] Test review_status updates correctly
- [ ] Deploy to Railway
- [ ] Run migration on Railway database

## Deployment Commands

```bash
cd d:\ai-recruitment-dashboard
git add .
git commit -m "Add resume assignment and review workflow"
git push origin main
```

After deployment, run migration on Railway:
```bash
# SSH into Railway or use Railway CLI
python migrate_resume_review.py
```
