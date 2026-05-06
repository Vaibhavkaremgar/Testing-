import logging
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas import JobApplicationCreate, JobApplicationResponse
from app.services.feeds import feed_registry
from app.services.jobs import JobDistributionService
from app.services.public_jobs import (
    build_location,
    build_public_apply_url,
    get_public_job_or_404,
    log_feed_access,
    normalize_skills,
    create_job_application,
)
from app.utils.uploads import save_resume_upload

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Job Feeds"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


def _build_feed_response(request: Request, db: Session, portal_name: str) -> Response:
    jobs = JobDistributionService.list_active_jobs(db)

    try:
        xml_content = feed_registry.get(portal_name).build_feed(jobs)
        JobDistributionService.mark_jobs_as_published(db, portal_name, jobs)
        log_feed_access(db, request, portal_name)
        return Response(
            content=xml_content,
            media_type="application/xml; charset=utf-8",
            headers={"Content-Type": "application/xml; charset=utf-8"},
        )
    except Exception as exc:
        logger.exception("Failed to generate %s feed", portal_name)
        JobDistributionService.mark_feed_failure(db, portal_name, str(exc))
        raise HTTPException(status_code=500, detail=f"Failed to generate {portal_name} feed")


@router.get("/jobs-feed.xml")
def default_jobs_feed(request: Request, db: Session = Depends(get_db)):
    return _build_feed_response(request, db, "default")


@router.get("/feeds/jooble.xml")
def jooble_feed(request: Request, db: Session = Depends(get_db)):
    return _build_feed_response(request, db, "jooble")


@router.get("/feeds/talent.xml")
def talent_feed(request: Request, db: Session = Depends(get_db)):
    return _build_feed_response(request, db, "talent")


@router.get("/feeds/jora.xml")
def jora_feed(request: Request, db: Session = Depends(get_db)):
    return _build_feed_response(request, db, "jora")


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
def public_job_detail(request: Request, job_id: UUID, db: Session = Depends(get_db)):
    job = get_public_job_or_404(db, job_id)
    skills = normalize_skills(job.skills)
    return templates.TemplateResponse(
        "jobs/detail.html",
        {
            "request": request,
            "job": job,
            "location": build_location(job),
            "skills": skills,
            "apply_url": build_public_apply_url(job),
            "page_title": f"{job.title} at {job.company_name or 'Company'}",
            "meta_description": (job.description or f"Apply for {job.title}").strip()[:155],
        },
    )


@router.post("/jobs/{job_id}/apply", response_model=JobApplicationResponse, status_code=status.HTTP_201_CREATED)
async def apply_to_job(
    job_id: UUID,
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    phone: str | None = Form(None),
    cover_letter: str | None = Form(None),
    resume: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    job = get_public_job_or_404(db, job_id)
    payload = JobApplicationCreate(
        full_name=full_name,
        email=email,
        phone=phone,
        cover_letter=cover_letter,
    )
    stored_resume = await save_resume_upload(resume)
    application = create_job_application(
        db,
        job=job,
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
        original_filename=stored_resume["original_filename"],
        stored_filename=stored_resume["stored_filename"],
        resume_url=stored_resume["resume_url"],
        cover_letter=payload.cover_letter,
    )

    if "text/html" in (request.headers.get("accept") or "").lower():
        return HTMLResponse(
            status_code=status.HTTP_201_CREATED,
            content=(
                "<!DOCTYPE html><html lang='en'><head><meta charset='UTF-8'>"
                "<meta name='viewport' content='width=device-width, initial-scale=1.0'>"
                "<title>Application Submitted</title></head><body "
                "style=\"font-family: Georgia, serif; background:#f6f4ee; color:#1f2933; padding:40px;\">"
                "<main style=\"max-width:720px; margin:0 auto; background:#fffdf8; border:1px solid #d9e2ec;"
                "border-radius:24px; padding:32px;\">"
                "<h1 style=\"margin-top:0;\">Application Submitted</h1>"
                "<p>Your application has been received successfully.</p>"
                f"<p><a href='/jobs/{job.id}' style='color:#0f766e;'>Return to job page</a></p>"
                "</main></body></html>"
            ),
        )

    return application
