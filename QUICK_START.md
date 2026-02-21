# 🚀 Quick Start Guide

## Start the Application (2 Steps)

### Step 1: Start Backend
Double-click **`START_BACKEND.bat`**
- Wait for "Application startup complete"
- Keep window open

### Step 2: Start Frontend  
Double-click **`START_FRONTEND.bat`**
- Wait for "Local: http://localhost:5173"
- Keep window open

### Step 3: Login
- Open: http://localhost:5173
- Email: `admin@talentai.com`
- Password: `admin123`

---

## 🔐 All Login Credentials

| Role | Email | Password |
|------|-------|----------|
| **Admin** | admin@talentai.com | admin123 |
| **Recruiter** | recruiter@talentai.com | recruiter123 |
| **Manager** | manager@talentai.com | manager123 |

---

## ❌ Getting "Failed to Fetch"?

**Solution:** Backend is not running!

1. Double-click `START_BACKEND.bat`
2. Wait for "Application startup complete"
3. Refresh browser

See **TROUBLESHOOTING.md** for detailed help.

---

## 📁 Project Structure

```
ai-recruitment-dashboard/
├── START_BACKEND.bat       ← Start backend server
├── START_FRONTEND.bat      ← Start frontend server
├── TROUBLESHOOTING.md      ← Fix common errors
├── backend/                ← Python FastAPI
│   ├── .env               ← Configuration
│   ├── app/
│   └── requirements.txt
└── frontend/               ← React + Vite
    ├── src/
    └── package.json
```

---

## 🎯 Key Features

✅ Resume upload & AI scoring (FREE with Groq)  
✅ Candidate pipeline (Kanban board)  
✅ Interview scheduling & tracking  
✅ Email automation (N8N integration)  
✅ Google Sheets sync  
✅ Analytics dashboard  

---

## 🆓 FREE AI Resume Scoring

1. Get FREE API key: https://console.groq.com
2. Add to `backend/.env`:
   ```env
   GROQ_API_KEY=gsk_your_key_here
   LLM_PROVIDER=groq
   ```
3. Restart backend
4. Upload resumes → Get AI scores!

**Scoring System:**
- Skills Match: 45% (most important)
- Experience: 25%
- Projects: 15%
- Education: 10%
- Soft Skills: 5%

See **RESUME_SCORING_METHODOLOGY.md** for details.

---

## 📊 Ports Used

- **Backend:** http://localhost:8000
- **Frontend:** http://localhost:5173
- **API Docs:** http://localhost:8000/api/docs

---

## 🛑 Stop Servers

Press **Ctrl+C** in each terminal window, or close the windows.

---

**Need Help?** Check **TROUBLESHOOTING.md**
