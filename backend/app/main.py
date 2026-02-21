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
    
    # Force delete old database if it exists and recreate
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(candidates)")
            columns = [column[1] for column in cursor.fetchall()]
            conn.close()
            
            # If predefined_questions column is missing, delete database
            if 'predefined_questions' not in columns:
                print("⚠️  Old database detected, deleting...")
                os.remove(db_path)
                print("✅ Database deleted, will recreate with correct schema")
        except Exception as e:
            print(f"⚠️  Migration check error: {e}")

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

# CORS middleware - MUST be first middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
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
