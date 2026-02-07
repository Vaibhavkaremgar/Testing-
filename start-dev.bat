@echo off
echo 🚀 Starting TalentAI Development Environment...

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python is not installed. Please install Python 3.11+
    pause
    exit /b 1
)

REM Check if Node.js is installed
node --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Node.js is not installed. Please install Node.js 18+
    pause
    exit /b 1
)

REM Backend setup
echo 📦 Setting up backend...
cd backend

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating Python virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate

REM Install dependencies
echo Installing Python dependencies...
pip install -r requirements.txt

REM Copy environment file if it doesn't exist
if not exist ".env" (
    echo Creating .env file...
    copy .env.example .env
)

REM Start backend in background
echo 🔧 Starting backend server...
start "Backend Server" cmd /k "uvicorn app.main:app --reload --port 8000"

cd ..

REM Frontend setup
echo 📦 Setting up frontend...
cd frontend

REM Install dependencies
echo Installing Node.js dependencies...
call npm install

REM Start frontend
echo 🎨 Starting frontend server...
start "Frontend Server" cmd /k "npm run dev"

cd ..

echo ✅ Development environment started!
echo 📊 Frontend: http://localhost:5173
echo 🔧 Backend API: http://localhost:8000
echo 📚 API Docs: http://localhost:8000/api/docs
echo.
echo Press any key to exit...
pause >nul