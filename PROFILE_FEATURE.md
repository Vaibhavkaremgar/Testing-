# User Profile & Admin Management Feature

## Overview
Complete user profile management system with avatar upload, personal information, and admin user management capabilities.

## Features

### User Profile (`/profile`)
- **Profile Picture Upload**: Upload and display avatar images (JPG, PNG, GIF)
- **Personal Information**: Full name, email, phone, department, bio
- **Role Display**: View current role badge
- **Real-time Updates**: Changes reflect immediately after save

### Admin User Management (`/admin/users`)
**Admin Only** - Manage all system users

- **User List**: View all users with avatars, roles, and status
- **User Statistics**: Total users, admins, recruiters, active users
- **Search**: Filter users by name, email, or role
- **Edit Users**: Update name, email, role, and active status
- **Delete Users**: Remove users (cannot delete own account)
- **Role Management**: Assign admin, recruiter, hiring_manager, or viewer roles

## Setup

### 1. Run Database Migration
```bash
cd backend
python migrate_user_profile.py
```

### 2. Create Uploads Directory
```bash
mkdir -p uploads/avatars
```

### 3. Restart Backend
```bash
uvicorn app.main:app --reload --port 8000
```

## API Endpoints

### Profile Management
- `PUT /api/auth/profile` - Update user profile
- `POST /api/auth/profile/avatar` - Upload avatar image

### Admin Endpoints (Admin Only)
- `GET /api/auth/users` - Get all users
- `PUT /api/auth/users/{user_id}` - Update user
- `DELETE /api/auth/users/{user_id}` - Delete user

## Database Schema

### New User Fields
```sql
phone VARCHAR(50)           -- Phone number
department VARCHAR(255)     -- Department name
bio TEXT                    -- User biography
avatar_url VARCHAR(500)     -- Avatar image path
```

## Frontend Routes

- `/profile` - User profile page (all users)
- `/admin/users` - User management page (admin only)

## Navigation

- **Profile**: Click avatar in header → "Profile"
- **Admin Users**: Sidebar → "Users" (admin only)

## Security

- Avatar uploads restricted to image files only
- Admin endpoints protected with role-based access control
- Users cannot delete their own accounts
- Email uniqueness validation

## File Storage

Avatars stored in: `backend/uploads/avatars/`
Format: `user_{user_id}.{ext}`

**Note**: For production, use cloud storage (S3, Cloudinary) or Railway Volumes for persistent storage.

## Usage

### Update Your Profile
1. Navigate to `/profile`
2. Click camera icon to upload avatar
3. Update personal information
4. Click "Save Changes"

### Manage Users (Admin)
1. Navigate to `/admin/users`
2. Search for users
3. Click edit icon to modify user
4. Update role, status, or details
5. Click "Save Changes"

## Permissions

| Feature | Admin | Recruiter | Hiring Manager | Viewer |
|---------|-------|-----------|----------------|--------|
| View own profile | ✅ | ✅ | ✅ | ✅ |
| Edit own profile | ✅ | ✅ | ✅ | ✅ |
| View all users | ✅ | ❌ | ❌ | ❌ |
| Edit users | ✅ | ❌ | ❌ | ❌ |
| Delete users | ✅ | ❌ | ❌ | ❌ |
| Change roles | ✅ | ❌ | ❌ | ❌ |
