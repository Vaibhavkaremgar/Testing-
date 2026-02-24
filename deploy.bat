@echo off
echo ========================================
echo   Deploying Diagnostic Funnel Changes
echo ========================================
echo.

echo [1/5] Checking Git status...
git status
echo.

echo [2/5] Adding changes...
git add backend/app/routes/diagnostic_funnel.py
git add backend/app/main.py
git add frontend/src/components/DiagnosticFunnel.jsx
git add frontend/src/lib/api.js
git add frontend/src/pages/Dashboard.jsx
git add DIAGNOSTIC_FUNNEL.md
git add DIAGNOSTIC_FUNNEL_SUMMARY.md
git add DIAGNOSTIC_FUNNEL_VISUAL.md
git add DEPLOYMENT_GUIDE.md
echo Changes staged!
echo.

echo [3/5] Committing changes...
git commit -m "Add diagnostic hiring funnel with AI-powered drop-off analysis and remove advanced analytics sections"
echo.

echo [4/5] Pushing to repository...
git push origin main
echo.

echo [5/5] Deployment initiated!
echo.
echo ========================================
echo   Next Steps:
echo ========================================
echo.
echo Backend: Railway will auto-deploy (check dashboard)
echo Frontend: Run deployment command for your platform:
echo.
echo   Netlify:  cd frontend ^&^& npm run build ^&^& netlify deploy --prod --dir=dist
echo   Vercel:   cd frontend ^&^& vercel --prod
echo.
echo ========================================
echo   Verify Deployment:
echo ========================================
echo.
echo 1. Check backend: https://your-backend.railway.app/api/health
echo 2. Test endpoint: https://your-backend.railway.app/api/analytics/diagnostic-funnel
echo 3. Open frontend and verify Dashboard shows diagnostic funnel
echo.
echo Deployment script complete!
pause
