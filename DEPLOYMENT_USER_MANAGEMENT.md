# Deployment Instructions - User Management Features

## Changes Made:

### 1. Add User Functionality
- Added "Add User" button in Admin Users page
- Dialog form with fields: Full Name, Email, Password, Role
- Creates new user account via `/api/auth/register` endpoint

### 2. Online/Offline Status Tracking
- Added `last_login_at` column to users table
- Tracks when user logs in
- Shows "Online" if logged in within last 15 minutes
- Shows "Offline" otherwise

## Deployment Steps:

### 1. Run Database Migration
```bash
cd backend
python migrate.py
```

This adds the `last_login_at` column to the users table.

### 2. Commit and Push Changes
```bash
git add .
git commit -m "Add user management: Add User button and Online/Offline status tracking"
git push origin main
```

### 3. Restart Backend
```bash
# If using PM2
pm2 restart ai-recruitment-backend

# If running manually
cd backend
uvicorn app.main:app --reload --port 8000
```

### 4. Rebuild Frontend
```bash
cd frontend
npm run build
```

## Features:

### Admin Users Page:
1. **Add User Button** - Creates new users with role assignment
2. **Status Column** - Shows Online (green) or Offline (gray)
3. **Online Detection** - User is online if logged in within 15 minutes

### How It Works:
- When user logs in → `last_login_at` is updated
- Backend checks if `last_login_at` is within 15 minutes
- Frontend displays Online/Offline badge accordingly

## Testing:
1. Login as admin
2. Go to Users tab
3. Click "Add User" button
4. Fill form and create user
5. Check status column - should show "Online" for recently logged in users
6. Wait 15+ minutes or logout - status changes to "Offline"
