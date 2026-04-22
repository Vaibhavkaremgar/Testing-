from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
import logging
import os
from starlette.middleware.base import BaseHTTPMiddleware

from app.ats_warmup import get_ats_warmup_state, run_ats_warmup
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.notification_service import ensure_default_email_templates
from app.routes import (
    agencies,
    analytics,
    async_interviews,
    auth,
    candidates,
    clients,
    communications,
    dashboard,
    email,
    email_templates,
    interviews,
    jobs,
    notifications,
    payment,
    pricing,
    subscriptions,
    wallet,
    webhooks,
)
from app.routes import settings as settings_routes
logger = logging.getLogger(__name__)


class CacheControlMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        path = request.url.path

        if path.startswith("/uploads/"):
            response.headers.setdefault("Cache-Control", "public, max-age=86400")
        elif path == "/" or path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-cache, no-store, must-revalidate")

        return response


def run_migrations():
    from app.migrations import run_migrations as run_auto_migrations

    try:
        run_auto_migrations()
    except Exception as exc:
        print(f"Migration warning: {exc}")


run_migrations()

try:
    Base.metadata.create_all(bind=engine)
    print("Database initialization complete")
except Exception as exc:
    print(f"create_all warning (non-fatal): {exc}")


app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered recruitment system API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

cors_options = {
    "allow_origins": settings.allowed_origins_list,
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
if settings.allowed_origin_regex:
    cors_options["allow_origin_regex"] = settings.allowed_origin_regex

app.add_middleware(CORSMiddleware, **cors_options)
# Compress JSON-heavy list responses so refreshes move less data over the wire.
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(CacheControlMiddleware)

try:
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
except Exception as exc:
    print(f"Warning: Could not create uploads directory: {exc}")

try:
    app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")
except Exception as exc:
    print(f"Warning: Could not mount uploads directory: {exc}")


app.include_router(auth.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(candidates.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(interviews.router, prefix="/api")
app.include_router(interviews.recording_router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(email_templates.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(settings_routes.router, prefix="/api")
app.include_router(clients.router, prefix="/api")
app.include_router(webhooks.router, prefix="/api")
app.include_router(email.router, prefix="/api")
app.include_router(communications.router)
app.include_router(async_interviews.router)
app.include_router(wallet.router, prefix="/api")
app.include_router(payment.router, prefix="/api")
app.include_router(agencies.router, prefix="/api")
app.include_router(pricing.router, prefix="/api")
app.include_router(subscriptions.router, prefix="/api")


@app.on_event("startup")
async def startup_event():
    logger.info("Startup event triggered")
    logger.info("Blocking ATS warmup starting")

    db = SessionLocal()
    try:
        ensure_default_email_templates(db)
    finally:
        db.close()

    print("[STARTUP] Pre-warming spaCy...")
    from app.spacy_nlp import get_nlp
    get_nlp()
    print("[STARTUP] spaCy ready.")
    print("[STARTUP] Pre-warming SkillIntelligence...")
    from ats.extraction.skill_intelligence import get_skill_engine
    get_skill_engine()
    print("[STARTUP] SkillIntelligence ready.")

    print("[STARTUP] Pre-warming domain classifier...")
    from ats.extraction.resume_type_detection import get_domain_classifier
    get_domain_classifier()
    print("[STARTUP] Domain classifier ready.")

    print("[STARTUP] All systems ready. Accepting requests.")

    try:
        logger.info("Running ATS warmup")
        warmup_result = run_ats_warmup(force=False)
        if not warmup_result.get("ready"):
            logger.warning("ATS warmup did not complete successfully — continuing anyway")
        else:
            logger.info("ATS warmup complete: ready=%s duration_ms=%s", warmup_result.get("ready"), warmup_result.get("duration_ms"))
    except Exception as exc:
        logger.exception("ATS warmup failed during startup: %s — continuing anyway", exc)

    logger.info("Application started successfully")


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "environment": settings.environment_name,
        "cors": {
            "enabled": True,
            "allowed_origins": settings.allowed_origins_list,
        },
        "warmup": get_ats_warmup_state(),
    }


@app.get("/api/warmup")
def warmup(force: bool = False):
    return run_ats_warmup(force=force)


@app.get("/api/test-db")
def test_db():
    try:
        from app.models import JobDescription

        db = SessionLocal()
        jobs = db.query(JobDescription).all()
        db.close()
        return {
            "status": "success",
            "jobs_count": len(jobs),
            "jobs": [{"id": j.id, "title": j.title, "is_active": j.is_active} for j in jobs],
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@app.get("/")
def root():
    return {
        "message": "Welcome to TalentAI Recruitment System API",
        "docs": "/api/docs",
        "health": "/api/health",
    }
