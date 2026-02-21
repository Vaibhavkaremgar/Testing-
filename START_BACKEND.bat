@echo off
echo Starting TalentAI Backend Server...
cd backend
call venv\Scripts\activate
echo Backend server starting on http://localhost:8000
uvicorn app.main:app --reload --port 8000
pause
