import time

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import hashlib
import logging
import os
import traceback
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.ats_warmup import get_ats_warmup_state, run_ats_warmup
from app.config import settings
from app.core.logging import setup_logging
from app.database import Base, SessionLocal, engine
from app.notification_service import ensure_default_email_templates
from app.services.portals import ensure_default_job_portals
from app.services.billing_service import ensure_plan_catalog
from app.routes import (
    agencies,
    analytics,
    async_interviews,
    auth,
    billing,
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
    usage,
    wallet,
    webhooks,
)
from app.routes import job_distribution, job_feeds
from app.routes import settings as settings_routes
logger = logging.getLogger(__name__)

setup_logging()


class CacheControlMiddleware(BaseHTTPMiddleware):
    API_CACHE_EXCLUDE_PREFIXES = (
        "/api/docs",
        "/api/redoc",
        "/api/openapi.json",
        "/api/warmup",
    )

    @staticmethod
    def _append_vary(existing_value: str, *values: str) -> str:
        parts = [part.strip() for part in (existing_value or "").split(",") if part.strip()]
        seen = {part.lower() for part in parts}
        for value in values:
            if value.lower() not in seen:
                parts.append(value)
                seen.add(value.lower())
        return ", ".join(parts)

    @staticmethod
    def _strip_body_headers(headers: dict) -> dict:
        blocked_headers = {
            "content-length",
            "content-encoding",
            "transfer-encoding",
        }
        return {
            key: value
            for key, value in dict(headers).items()
            if key.lower() not in blocked_headers
        }

    @classmethod
    def _should_apply_api_cache(cls, request: Request, response) -> bool:
        if request.method not in {"GET", "HEAD"}:
            return False
        if response.status_code != 200:
            return False
        path = request.url.path
        if not path.startswith("/api/"):
            return False
        if any(path.startswith(prefix) for prefix in cls.API_CACHE_EXCLUDE_PREFIXES):
            return False
        if "range" in request.headers:
            return False
        content_type = (response.headers.get("content-type") or "").lower()
        return "application/json" in content_type

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        path = request.url.path

        if path.startswith("/uploads/"):
            response.headers.setdefault("Cache-Control", "public, max-age=86400")
        elif path == "/":
            response.headers.setdefault("Cache-Control", "no-cache, no-store, must-revalidate")
        elif self._should_apply_api_cache(request, response):
            body = b""
            async for chunk in response.body_iterator:
                body += chunk

            etag = f'W/"{hashlib.sha256(body).hexdigest()}"'
            cache_headers = dict(response.headers)
            cache_headers["Cache-Control"] = "private, no-cache, max-age=0, must-revalidate"
            cache_headers["ETag"] = etag
            cache_headers["Vary"] = self._append_vary(
                cache_headers.get("Vary", ""),
                "Authorization",
                "Accept-Encoding",
            )

            if request.headers.get("if-none-match") == etag:
                cache_headers = self._strip_body_headers(cache_headers)
                return Response(
                    status_code=304,
                    headers=cache_headers,
                    background=response.background,
                )

            return Response(
                content=body,
                status_code=response.status_code,
                headers=cache_headers,
                media_type=response.media_type,
                background=response.background,
            )
        elif path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-cache, no-store, must-revalidate")

        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        started_at = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            logger.exception(
                "Unhandled request failure method=%s path=%s duration_ms=%s",
                request.method,
                request.url.path,
                duration_ms,
            )
            raise

        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.info(
            "Request completed method=%s path=%s status=%s duration_ms=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
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
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(CacheControlMiddleware)

try:
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
except Exception as exc:
    print(f"Warning: Could not create uploads directory: {exc}")

try:
    app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")
except Exception as exc:
    print(f"Warning: Could not mount uploads directory: {exc}")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning("Validation error path=%s errors=%s", request.url.path, exc.errors())
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Request validation failed",
            "errors": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Unhandled exception path=%s error=%s traceback=%s",
        request.url.path,
        exc,
        "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


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
app.include_router(billing.router, prefix="/api")
app.include_router(wallet.router, prefix="/api")
app.include_router(payment.router, prefix="/api")
app.include_router(agencies.router, prefix="/api")
app.include_router(pricing.router, prefix="/api")
app.include_router(subscriptions.router, prefix="/api")
app.include_router(usage.router, prefix="/api")
app.include_router(job_distribution.router, prefix="/api")
app.include_router(job_feeds.router)


@app.on_event("startup")
async def startup_event():
    logger.info("Startup event triggered")
    logger.info("Blocking ATS warmup starting")

    db = SessionLocal()
    try:
        ensure_plan_catalog(db)
        ensure_default_email_templates(db)
        ensure_default_job_portals(db)
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
