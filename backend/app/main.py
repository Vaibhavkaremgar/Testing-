from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import sqlite3
from app.config import settings
from app.database import engine, Base
from app.routes import auth, candidates, jobs, interviews, analytics, email_templates, clients, webhooks, email, communications, async_interviews
from app.routes import settings as settings_routes
from app.seed import seed_database

# Run migrations BEFORE creating tables
def run_migrations():
    """Add missing columns to Railway database"""
    # Check both local and Railway database paths
    db_paths = ["talentai.db", "/data/app.db"]
    db_path = None
    
    for path in db_paths:
        if os.path.exists(path):
            db_path = path
            break
    
    if not db_path:
        print("⚠️ No database found, will create new one")
        return
    
    print(f"🔧 Running migrations on {db_path}...")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Add missing interview columns to candidates table
        cursor.execute("PRAGMA table_info(candidates)")
        columns = [col[1] for col in cursor.fetchall()]
        
        missing_cols = [
            ('interview_video_url', 'VARCHAR(500)'),
            ('interview_transcript', 'TEXT'),
            ('interview_ai_summary', 'TEXT'),
            ('interview_technical_score', 'FLOAT'),
            ('interview_communication_score', 'FLOAT'),
            ('interview_culture_fit_score', 'FLOAT')
        ]
        
        for col_name, col_type in missing_cols:
            if col_name not in columns:
                try:
                    cursor.execute(f"ALTER TABLE candidates ADD COLUMN {col_name} {col_type}")
                    print(f"✅ Added {col_name} column")
                except Exception as e:
                    print(f"⚠️ Could not add {col_name}: {e}")
        
        # Add user profile columns
        cursor.execute("PRAGMA table_info(users)")
        user_columns = [col[1] for col in cursor.fetchall()]
        
        user_cols = [
            ('phone', 'VARCHAR(50)'),
            ('department', 'VARCHAR(255)'),
            ('bio', 'TEXT'),
            ('avatar_url', 'VARCHAR(500)')
        ]
        
        for col_name, col_type in user_cols:
            if col_name not in user_columns:
                try:
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                    print(f"✅ Added {col_name} to users")
                except Exception as e:
                    print(f"⚠️ Could not add {col_name}: {e}")
        
        conn.commit()
        conn.close()
        print("✅ Migration complete")
    except Exception as e:
        print(f"❌ Migration error: {e}")
        import traceback
        traceback.print_exc()

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

# CORS middleware - Allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create uploads directory
try:
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
except Exception as e:
    print(f"Warning: Could not create uploads directory: {e}")

# Mount static files for uploads
try:
    app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")
except Exception as e:
    print(f"Warning: Could not mount uploads directory: {e}")

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
app.include_router(email.router, prefix="/api")
app.include_router(communications.router)
app.include_router(async_interviews.router)

@app.on_event("startup")
async def startup_event():
    print("✅ Application started successfully")

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "app": settings.APP_NAME, "cors": "enabled"}

@app.get("/api/test-db")
def test_db():
    """Test database connection"""
    try:
        from app.database import SessionLocal
        from app.models import JobDescription
        db = SessionLocal()
        jobs = db.query(JobDescription).all()
        db.close()
        return {
            "status": "success",
            "jobs_count": len(jobs),
            "jobs": [{"id": j.id, "title": j.title, "is_active": j.is_active} for j in jobs]
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.get("/")
def root():
    return {
        "message": "Welcome to TalentAI Recruitment System API",
        "docs": "/api/docs",
        "health": "/api/health"
    }
