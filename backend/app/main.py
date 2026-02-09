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
    """Run database migrations - CRITICAL for Railway deployment"""
    db_path = "recruitment.db"
    
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
        else:
            print("ℹ️  Candidates table doesn't exist yet, will be created by SQLAlchemy")
        
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
    # Final verification that summary column exists
    import sqlite3
    try:
        conn = sqlite3.connect("recruitment.db")
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(candidates)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'summary' in columns:
            print("✅ VERIFIED: 'summary' column exists in database")
        else:
            print("⚠️  WARNING: 'summary' column missing! Attempting to add...")
            cursor.execute("ALTER TABLE candidates ADD COLUMN summary TEXT")
            conn.commit()
            print("✅ 'summary' column added in startup event")
        conn.close()
    except Exception as e:
        print(f"❌ Startup verification error: {e}")
    
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
