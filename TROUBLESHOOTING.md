# 🔧 Troubleshooting: "Failed to Fetch" Error

## Problem
Getting "Failed to fetch" error when trying to login or upload resumes.

## Root Cause
The **backend server is not running** on port 8000.

---

## ✅ Quick Fix (Use Startup Scripts)

### Option 1: Use the Batch Files (Easiest)

1. **Start Backend:**
   - Double-click `START_BACKEND.bat` in the project root
   - Wait for "Application startup complete"
   - Keep this window open

2. **Start Frontend:**
   - Double-click `START_FRONTEND.bat` in the project root
   - Wait for "Local: http://localhost:5173"
   - Keep this window open

3. **Access Application:**
   - Open browser: http://localhost:5173
   - Login with: `admin@talentai.com` / `admin123`

---

## 🔧 Manual Fix (If Batch Files Don't Work)

### Step 1: Start Backend Server

Open **Command Prompt** or **PowerShell**:

```bash
cd d:\ai-recruitment-dashboard\backend
venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

**Expected Output:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

**Keep this terminal open!**

---

### Step 2: Start Frontend Server

Open **NEW Command Prompt** or **PowerShell**:

```bash
cd d:\ai-recruitment-dashboard\frontend
npm run dev
```

**Expected Output:**
```
VITE v5.x.x  ready in xxx ms

➜  Local:   http://localhost:5173/
➜  Network: use --host to expose
```

**Keep this terminal open too!**

---

### Step 3: Access Application

1. Open browser: **http://localhost:5173**
2. Login with:
   - Email: `admin@talentai.com`
   - Password: `admin123`

---

## 🔍 Verify Backend is Running

### Check if port 8000 is listening:

```bash
netstat -ano | findstr :8000
```

**Expected Output:**
```
TCP    0.0.0.0:8000    0.0.0.0:0    LISTENING    12345
```

### Test API directly:

Open browser: **http://localhost:8000/api/docs**

You should see the **FastAPI Swagger UI** documentation.

---

## ❌ Common Errors & Solutions

### Error 1: "Port 8000 is already in use"

**Solution:**
```bash
# Kill existing Python processes
taskkill /F /IM python.exe

# Then restart backend
cd backend
venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

---

### Error 2: "SECRET_KEY environment variable is required"

**Solution:**
Check `backend/.env` file exists and has:
```env
SECRET_KEY=your-secret-key-min-32-characters-long-change-this-in-production
```

---

### Error 3: "venv\Scripts\activate : cannot be loaded"

**Solution (PowerShell):**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then try activating venv again.

---

### Error 4: "Module not found" errors

**Solution:**
```bash
cd backend
venv\Scripts\activate
pip install -r requirements.txt
```

---

### Error 5: Frontend shows "Failed to fetch" but backend is running

**Solution:**

1. Check CORS settings in `backend/.env`:
   ```env
   ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
   ```

2. Restart backend server

3. Clear browser cache (Ctrl+Shift+Delete)

4. Try in incognito/private window

---

## 🔐 Login Credentials

### Admin Account:
- **Email:** `admin@talentai.com`
- **Password:** `admin123`

### Recruiter Account:
- **Email:** `recruiter@talentai.com`
- **Password:** `recruiter123`

### Hiring Manager Account:
- **Email:** `manager@talentai.com`
- **Password:** `manager123`

---

## 📊 System Requirements

- **Python:** 3.10 or 3.11
- **Node.js:** 18+
- **Ports:** 8000 (backend), 5173 (frontend)

---

## 🚀 Production Deployment

For Railway/Heroku/AWS deployment, the backend starts automatically.

**Check deployment logs:**
```bash
# Railway
railway logs

# Heroku
heroku logs --tail
```

---

## 📞 Still Having Issues?

1. **Check backend logs** in the terminal where you started the backend
2. **Check browser console** (F12 → Console tab)
3. **Verify both servers are running** (backend on 8000, frontend on 5173)
4. **Try different browser** (Chrome, Firefox, Edge)
5. **Disable browser extensions** (especially ad blockers)

---

## ✅ Success Checklist

- [ ] Backend running on http://localhost:8000
- [ ] Frontend running on http://localhost:5173
- [ ] Can access http://localhost:8000/api/docs
- [ ] Can access http://localhost:5173
- [ ] Can login with admin@talentai.com / admin123
- [ ] No errors in browser console (F12)
- [ ] No errors in backend terminal

---

**Last Updated:** 2024
**System:** TalentAI Recruitment Dashboard
