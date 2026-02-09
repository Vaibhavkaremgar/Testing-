from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import sqlite3
from app.config import settings
from app.database import engine, Base
from app.routes import auth, candidates, jobs, interviews, analytics, email_templates, clients, webhooks, communications
from app.routes import settings as settings_routes
from app.seed import seed_database

# Run migrations BEFORE creating tables
def run_migrations():
    """Run database migrations"""
    db_path = "recruitment.db"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if candidates table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='candidates'")
        if cursor.fetchone():
            # Check if summary column exists
            cursor.execute("PRAGMA table_info(candidates)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'summary' not in columns:
                print("Running migration: Adding 'summary' column to candidates table...")
                cursor.execute("ALTER TABLE candidates ADD COLUMN summary TEXT")
                conn.commit()
                print("✓ Migration complete: 'summary' column added")
        
        conn.close()
    except Exception as e:
        print(f"Migration error: {e}")

run_migrations()

# Create database tables
Base.metadata.create_all(bind=engine)

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
    allow_origins=settings.allowed_origins_list,
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

@app.on_event("startup")
async def startup_event():
    """Seed database with initial data on startup"""
    # Seeding enabled for demo data
    seed_database()
    pass

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "app": settings.APP_NAME}

@app.get("/")
def root():
    return {
        "message": "Welcome to TalentAI Recruitment System API",
        "docs": "/api/docs",
        "health": "/api/health"
    }
