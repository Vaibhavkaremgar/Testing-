# Deployment Guide - Diagnostic Funnel Feature

## Changes Summary

### Backend
- ✅ New route: `backend/app/routes/diagnostic_funnel.py`
- ✅ Updated: `backend/app/main.py` (added route import)

### Frontend
- ✅ New component: `frontend/src/components/DiagnosticFunnel.jsx`
- ✅ Updated: `frontend/src/lib/api.js` (added API method)
- ✅ Updated: `frontend/src/pages/Dashboard.jsx` (removed sections, added diagnostic funnel)

---

## Deployment Steps

### Option 1: Local Testing First

#### 1. Backend
```bash
cd backend

# Install dependencies (if needed)
pip install -r requirements.txt

# Start backend
uvicorn app.main:app --reload --port 8000
```

#### 2. Frontend
```bash
cd frontend

# Install dependencies (if needed)
npm install

# Build for production
npm run build

# Or run dev mode
npm run dev
```

#### 3. Test
- Open http://localhost:5173 (dev) or http://localhost:4173 (preview)
- Navigate to Dashboard
- Verify diagnostic funnel appears
- Test "Why?" buttons

---

### Option 2: Deploy to Railway (Production)

#### Backend Deployment

1. **Commit changes:**
```bash
git add .
git commit -m "Add diagnostic hiring funnel with AI-powered drop-off analysis"
git push origin main
```

2. **Railway auto-deploys** (if connected to GitHub)
   - Railway detects changes
   - Rebuilds backend automatically
   - New route available at: `https://your-backend.railway.app/api/analytics/diagnostic-funnel`

3. **Verify backend:**
```bash
curl https://your-backend.railway.app/api/health
curl https://your-backend.railway.app/api/analytics/diagnostic-funnel \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Frontend Deployment

1. **Update environment variables** (if needed):
```bash
# frontend/.env.production
VITE_API_URL=https://your-backend.railway.app
```

2. **Build frontend:**
```bash
cd frontend
npm run build
```

3. **Deploy to Netlify/Vercel:**

**Netlify:**
```bash
# Install Netlify CLI
npm install -g netlify-cli

# Deploy
cd frontend
netlify deploy --prod --dir=dist
```

**Vercel:**
```bash
# Install Vercel CLI
npm install -g vercel

# Deploy
cd frontend
vercel --prod
```

---

### Option 3: Docker Deployment

#### 1. Build Docker images:
```bash
# Backend
cd backend
docker build -t ai-recruitment-backend .

# Frontend
cd frontend
docker build -t ai-recruitment-frontend .
```

#### 2. Run with Docker Compose:
```bash
# From root directory
docker-compose up -d
```

#### 3. Verify:
```bash
docker-compose ps
docker-compose logs -f
```

---

## Environment Variables

### Backend (.env)
```env
# Required
DATABASE_URL=sqlite:///./talentai.db
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Optional (for AI features)
GROQ_API_KEY=gsk_your_groq_key_here
LLM_PROVIDER=groq
```

### Frontend (.env.production)
```env
VITE_API_URL=https://your-backend-url.railway.app
```

---

## Post-Deployment Checklist

### Backend
- [ ] Health check passes: `/api/health`
- [ ] New endpoint works: `/api/analytics/diagnostic-funnel`
- [ ] Authentication working
- [ ] Database accessible
- [ ] Groq API key configured (optional)

### Frontend
- [ ] Dashboard loads without errors
- [ ] Diagnostic funnel displays
- [ ] "Why?" buttons open modal
- [ ] API calls succeed
- [ ] No console errors

### Testing
- [ ] Upload test candidates
- [ ] Verify funnel calculations
- [ ] Test AI reason generation
- [ ] Check abnormal detection
- [ ] Test on mobile/tablet

---

## Quick Deploy Commands

### Full Stack (Local)
```bash
# Terminal 1 - Backend
cd backend && uvicorn app.main:app --reload

# Terminal 2 - Frontend
cd frontend && npm run dev
```

### Production Build
```bash
# Backend (Railway auto-deploys on push)
git add . && git commit -m "Deploy diagnostic funnel" && git push

# Frontend (Netlify)
cd frontend && npm run build && netlify deploy --prod --dir=dist
```

---

## Rollback Plan

If issues occur:

### Backend
```bash
# Revert commit
git revert HEAD
git push origin main

# Or remove route manually
# Comment out in backend/app/main.py:
# app.include_router(diagnostic_funnel.router, prefix="/api")
```

### Frontend
```bash
# Revert commit
git revert HEAD
git push origin main

# Or deploy previous build
netlify rollback
```

---

## Monitoring

### Check Logs

**Railway:**
```bash
railway logs
```

**Local:**
```bash
# Backend
tail -f backend/server.log

# Frontend
# Check browser console
```

### Performance
- Backend response time: <100ms (without AI)
- AI generation: 0.5-1s per reason
- Frontend render: <50ms

---

## Troubleshooting

### Backend Issues

**Route not found:**
```bash
# Verify route is registered
curl http://localhost:8000/api/docs
# Look for /analytics/diagnostic-funnel
```

**Import error:**
```bash
# Check Python path
cd backend
python -c "from app.routes import diagnostic_funnel"
```

### Frontend Issues

**Component not rendering:**
```bash
# Check build
cd frontend
npm run build
# Look for DiagnosticFunnel.jsx in output
```

**API call fails:**
```bash
# Check CORS
# Verify API_BASE in frontend/src/lib/api.js
```

---

## Success Indicators

✅ Backend health check returns 200
✅ Diagnostic funnel endpoint returns data
✅ Frontend builds without errors
✅ Dashboard displays new funnel
✅ Modal opens on "Why?" click
✅ AI reasons generate (if Groq configured)
✅ No console errors
✅ Mobile responsive

---

## Support

If deployment fails:
1. Check logs for errors
2. Verify environment variables
3. Test locally first
4. Review DIAGNOSTIC_FUNNEL.md
5. Check Railway/Netlify dashboard

**Your changes are ready to deploy!** 🚀
