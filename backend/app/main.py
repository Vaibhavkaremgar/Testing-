from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import sqlite3
from app.config import settings
from app.database import engine, Base
from app.routes import auth, candidates, jobs, interviews, analytics, email_templates, clients, webhooks, communications, async_interviews
from app.routes import settings as settings_routes
from app.seed import seed_database

# Run migrations BEFORE creating tables
def run_migrations():
    """Run database migrations - CRITICAL for Railway deployment"""
    db_path = "talentai.db"
    
    try:
        # Ensure database file exists
        if not os.path.exists(db_path):
            print("✅ Database doesn't exist yet, will be created by SQLAlchemy")
            return
            
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if job_descriptions table has interview_questions column
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='job_descriptions'")
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(job_descriptions)")
                job_columns = [column[1] for column in cursor.fetchall()]
                
                if 'interview_questions' not in job_columns:
                    print("⚠️  MIGRATION: Adding 'interview_questions' column to job_descriptions table...")
                    cursor.execute("ALTER TABLE job_descriptions ADD COLUMN interview_questions JSON")
                    conn.commit()
                    print("✅ MIGRATION COMPLETE: 'interview_questions' column added")
        except Exception as e:
            print(f"⚠️  Job migration skipped: {e}")
        
        # Check if candidates table exists
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='candidates'")
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(candidates)")
                columns = [column[1] for column in cursor.fetchall()]
                
                if 'summary' not in columns:
                    cursor.execute("ALTER TABLE candidates ADD COLUMN summary TEXT")
                    conn.commit()
                    print("✅ Added 'summary' column")
                
                if 'predefined_questions' not in columns:
                    cursor.execute("ALTER TABLE candidates ADD COLUMN predefined_questions TEXT")
                    conn.commit()
                    print("✅ Added 'predefined_questions' column")
        except Exception as e:
            print(f"⚠️  Candidate migration skipped: {e}")
        
        conn.close()
        print("✅ Migrations complete")
    except Exception as e:
        print(f"⚠️  Migration error: {e}")
        print("Continuing with startup...")

run_migrations()

# Create database tables
Base.metadata.create_all(bind=engine)

print("✅ Database initialization complete\n")

app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered recruitment system API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

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

# Create uploads directory
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

# Mount static files for uploads
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# Include routers
app.include_router(auth.router, prefix="/api")
app.include_router(candidates.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(interviews.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(email_templates.router, prefix="/api")
app.include_router(settings_routes.router, prefix="/api")
app.include_router(clients.router, prefix="/api")
app.include_router(webhooks.router, prefix="/api")
app.include_router(communications.router)
app.include_router(async_interviews.router)

@app.on_event("startup")
async def startup_event():
    print("✅ Application started successfully")

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "app": settings.APP_NAME, "cors": "enabled"}

@app.get("/")
def root():
    return {
        "message": "Welcome to TalentAI Recruitment System API",
        "docs": "/api/docs",
        "health": "/api/health"
    }
