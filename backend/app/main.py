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
            print("Database doesn't exist yet, will be created by SQLAlchemy")
            return
            
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if candidates table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='candidates'")
        if cursor.fetchone():
            # Check if summary column exists
            cursor.execute("PRAGMA table_info(candidates)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'summary' not in columns:
                print("⚠️  MIGRATION: Adding 'summary' column to candidates table...")
                cursor.execute("ALTER TABLE candidates ADD COLUMN summary TEXT")
                conn.commit()
                print("✅ MIGRATION COMPLETE: 'summary' column added successfully")
            else:
                print("✅ 'summary' column already exists")
            
            if 'display_status' not in columns:
                print("⚠️  MIGRATION: Adding 'display_status' column to candidates table...")
                cursor.execute("ALTER TABLE candidates ADD COLUMN display_status VARCHAR(50)")
                conn.commit()
                print("✅ MIGRATION COMPLETE: 'display_status' column added successfully")
            else:
                print("✅ 'display_status' column already exists")
            
            if 'predefined_questions' not in columns:
                print("⚠️  MIGRATION: Adding 'predefined_questions' column to candidates table...")
                cursor.execute("ALTER TABLE candidates ADD COLUMN predefined_questions TEXT")
                conn.commit()
                print("✅ MIGRATION COMPLETE: 'predefined_questions' column added successfully")
            else:
                print("✅ 'predefined_questions' column already exists")
        else:
            print("ℹ️  Candidates table doesn't exist yet, will be created by SQLAlchemy")
        
        # Check if job_descriptions table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='job_descriptions'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(job_descriptions)")
            job_columns = [column[1] for column in cursor.fetchall()]
            
            if 'interview_questions' not in job_columns:
                print("⚠️  MIGRATION: Adding 'interview_questions' column to job_descriptions table...")
                cursor.execute("ALTER TABLE job_descriptions ADD COLUMN interview_questions JSON")
                conn.commit()
                print("✅ MIGRATION COMPLETE: 'interview_questions' column added successfully")
            else:
                print("✅ 'interview_questions' column already exists")
        else:
            print("ℹ️  job_descriptions table doesn't exist yet, will be created by SQLAlchemy")
        
        conn.close()
    except Exception as e:
        print(f"❌ Migration error: {e}")
        print("Continuing with startup...")

run_migrations()

# Create database tables
Base.metadata.create_all(bind=engine)

# Run migrations AGAIN after table creation (for Railway)
print("\n♻️  Running post-creation migration check...")
run_migrations()
print("✅ Database initialization complete\n")

app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered recruitment system API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins temporarily
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
    """Seed database with initial data on startup"""
    import sqlite3
    import os
    
    # Get correct database path from environment or default
    db_url = os.getenv("DATABASE_URL", "sqlite:///./talentai.db")
    db_path = db_url.replace("sqlite:///./", "")
    print(f"📁 Using database: {db_path}")
    
    try:
        if not os.path.exists(db_path):
            print(f"⚠️ Database not found at {db_path}")
            return
            
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='candidates'")
        if not cursor.fetchone():
            print("⚠️ Candidates table doesn't exist")
            conn.close()
            return
        
        # CRITICAL: Fix RESUME_REJECTED values
        cursor.execute("SELECT COUNT(*) FROM candidates WHERE stage = 'resume_rejected'")
        count = cursor.fetchone()[0]
        if count > 0:
            print(f"⚠️ Found {count} candidates with 'resume_rejected' stage")
            print("🔄 Converting to 'rejected'...")
            cursor.execute("UPDATE candidates SET stage = 'rejected' WHERE stage = 'resume_rejected'")
            conn.commit()
            print(f"✅ Converted {count} candidates")
        else:
            print("✅ No resume_rejected values found")
        
        conn.close()
    except Exception as e:
        print(f"❌ Startup error: {e}")
        import traceback
        traceback.print_exc()
    
    seed_database()

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
