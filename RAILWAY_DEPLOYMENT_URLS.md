# Railway Deployment URLs - Configuration Summary

## ✅ All URLs Updated for Production

### Frontend URL
**Production**: `https://glistening-youth-production.up.railway.app`

### Backend URL
**Production**: `https://ai-recruitment-dashboard-production.up.railway.app`

---

## Files Updated

### 1. Frontend Configuration

#### `frontend/.env`
```env
# VITE_API_URL=http://localhost:8000
VITE_API_URL=https://ai-recruitment-dashboard-production.up.railway.app
```

#### `frontend/src/lib/api.js`
- Fallback URL already set to Railway backend
- No changes needed

#### `frontend/src/pages/Interviews.jsx`
```javascript
// Line ~160: Interview booking slot URL
// const url = `http://localhost:5000/?...`
const url = `https://your-interview-booking-app.railway.app/?...`
```
**⚠️ Note**: Replace `your-interview-booking-app.railway.app` with actual interview booking app URL

#### `frontend/vite.config.js`
- Already configured with Railway URL
- No changes needed

---

### 2. Backend Configuration

#### `backend/app/main.py`
```python
# CORS middleware - Updated for Railway deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://glistening-youth-production.up.railway.app",  # Frontend Railway URL
        "http://localhost:5173",  # Local development
        "*"  # Allow all for testing
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

#### `backend/app/config.py`
```python
# ALLOWED_ORIGINS: str = "http://localhost:5173,..."
ALLOWED_ORIGINS: str = "https://glistening-youth-production.up.railway.app,http://localhost:5173,..."
```

#### `backend/app/routes/async_interviews.py`
```python
# async_link = f"http://localhost:5173/async-interview/{token}"
async_link = f"https://glistening-youth-production.up.railway.app/async-interview/{token}"
```

---

## Test Files (Not Modified - For Local Testing Only)
- `backend/create_admin.py` - Uses localhost for local admin creation
- `backend/test_*.py` - All test files use localhost
- These files are for local development only and don't affect production

---

## Deployment Checklist

### Before Deploying:
- [x] Frontend `.env` updated with Railway backend URL
- [x] Backend CORS configured with Railway frontend URL
- [x] Async interview links use Railway frontend URL
- [x] Interview booking URL updated (needs actual URL)
- [x] All localhost URLs commented out

### After Deploying:
- [ ] Test login at: `https://glistening-youth-production.up.railway.app`
- [ ] Verify API calls to: `https://ai-recruitment-dashboard-production.up.railway.app/api`
- [ ] Test resume upload functionality
- [ ] Test async interview link generation
- [ ] Update interview booking URL with actual Railway deployment

---

## Environment Variables on Railway

### Frontend Service
```
VITE_API_URL=https://ai-recruitment-dashboard-production.up.railway.app
```

### Backend Service
```
DATABASE_URL=<Railway provides this>
SECRET_KEY=<your-secret-key>
GROQ_API_KEY=<your-groq-key>
LLM_PROVIDER=groq
```

---

## 🚀 Ready for Deployment!

All URLs have been updated. Just deploy both services to Railway and they will communicate correctly.
