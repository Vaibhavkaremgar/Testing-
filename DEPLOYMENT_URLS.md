# Deployment URLs Configuration

## Current Status

✅ **Frontend Vite Config**: No hardcoded URLs (accepts all Railway domains)
✅ **Backend Config**: Uses environment variables for CORS

## What You Need to Update

### 1. Backend CORS Configuration

**File**: `backend/app/config.py` (Line 28)

**Current**:
```python
ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
```

**Update to** (add your new Railway frontend URL):
```python
ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000,https://YOUR-NEW-FRONTEND-URL.up.railway.app"
```

**OR** set via Railway environment variable:
```
ALLOWED_ORIGINS=http://localhost:5173,https://YOUR-NEW-FRONTEND-URL.up.railway.app
```

### 2. Frontend Environment Variable

**Railway Frontend Service** - Add environment variable:
```
VITE_API_URL=https://YOUR-BACKEND-URL.up.railway.app
```

## No Changes Needed

✅ `frontend/vite.config.js` - Already configured to accept all hosts
✅ `frontend/src/lib/api.js` - Uses `VITE_API_URL` environment variable

## Summary

**What's already fixed:**
- Frontend accepts any Railway domain (no hardcoded URLs)
- Frontend API client reads backend URL from environment variable
- Safe JSON parsing for all API responses

**What you need to do:**
1. Get your new Railway frontend URL
2. Add it to backend CORS settings (either in code or environment variable)
3. Set `VITE_API_URL` in frontend Railway service to point to backend

That's it!
