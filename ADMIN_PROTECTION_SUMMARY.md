# Admin Role Protection - Implementation Summary

## Overview
Added admin role verification to all administrative API endpoints to ensure only users with admin role can perform privileged operations.

## Changes Made

### 1. Added Admin Check Function (`backend/app/auth.py`)
```python
async def get_current_admin_user(current_user: User = Depends(get_current_active_user)) -> User:
    from app.models import UserRole
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user
```

### 2. Protected Endpoints

#### Job Descriptions (`backend/app/routes/jobs.py`)
- ✅ `POST /api/jobs` - Create job (Admin only)
- ✅ `PUT /api/jobs/{id}` - Update job (Admin only)
- ✅ `DELETE /api/jobs/{id}` - Delete job (Admin only)
- ℹ️ `GET /api/jobs` - List jobs (All authenticated users)
- ℹ️ `GET /api/jobs/{id}` - Get job details (All authenticated users)

#### Email Templates (`backend/app/routes/email_templates.py`)
- ✅ `POST /api/email-templates` - Create template (Admin only)
- ✅ `PUT /api/email-templates/{id}` - Update template (Admin only)
- ✅ `DELETE /api/email-templates/{id}` - Delete template (Admin only)
- ℹ️ `GET /api/email-templates` - List templates (All authenticated users)
- ℹ️ `GET /api/email-templates/{id}` - Get template (All authenticated users)

#### Settings (`backend/app/routes/settings.py`)
- ✅ `POST /api/settings/resume-score` - Save settings (Admin only)
- ℹ️ `GET /api/settings/resume-score` - Get settings (All authenticated users)

#### User Management (`backend/app/routes/auth.py`) - Already Protected
- ✅ `GET /api/auth/users` - List all users (Admin only)
- ✅ `PUT /api/auth/users/{id}` - Update user (Admin only)
- ✅ `DELETE /api/auth/users/{id}` - Delete user (Admin only)

## How It Works

1. **Authentication Flow:**
   - User logs in → receives JWT token
   - Token contains user email
   - `get_current_user` validates token and retrieves user from database
   - `get_current_active_user` checks if user is active
   - `get_current_admin_user` checks if user has admin role

2. **Error Response:**
   - Status Code: `403 Forbidden`
   - Message: `"Admin access required"`

3. **Usage in Routes:**
   ```python
   @router.post("")
   def create_job(
       job: JobDescriptionCreate,
       db: Session = Depends(get_db),
       current_user: User = Depends(get_current_admin_user)  # ← Admin check
   ):
       # Only admins can reach this code
       ...
   ```

## Testing

### Test Admin Access (Should Succeed)
```bash
# Login as admin
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@company.com&password=admin123"

# Use token to create job
curl -X POST http://localhost:8000/api/jobs \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"title": "Test Job", ...}'
```

### Test Non-Admin Access (Should Fail with 403)
```bash
# Login as recruiter
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=recruiter@company.com&password=recruiter123"

# Try to create job (will fail)
curl -X POST http://localhost:8000/api/jobs \
  -H "Authorization: Bearer <recruiter_token>" \
  -H "Content-Type: application/json" \
  -d '{"title": "Test Job", ...}'

# Response: {"detail": "Admin access required"}
```

## Security Benefits

1. **Role-Based Access Control (RBAC):** Only admins can modify system configuration
2. **Data Integrity:** Prevents unauthorized users from creating/modifying jobs and templates
3. **Audit Trail:** Clear separation between admin and non-admin actions
4. **Principle of Least Privilege:** Users only have access to operations they need

## Notes

- All endpoints still require authentication (valid JWT token)
- Admin check is an additional layer on top of authentication
- Non-admin users can still view jobs, templates, and settings
- Candidate operations remain accessible to all authenticated users (with role-based filtering)
