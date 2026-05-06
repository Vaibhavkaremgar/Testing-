import logging
from pathlib import Path
from xml.etree import ElementTree as ET

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas import JobApplicationCreate, JobApplicationResponse
from app.services.feeds import feed_registry
from app.services.jobs import JobDistributionService
from app.services.public_jobs import (
    build_location,
    build_public_apply_url,
    build_public_job_url,
    get_job_canonical_path,
    get_public_job_by_reference_or_404,
    log_feed_access,
    normalize_skills,
    create_job_application,
)
from app.utils.job_schema import build_job_posting_schema, dump_job_posting_schema
from app.utils.uploads import save_resume_upload
from app.utils.xml_utils import append_text_element, prettify_xml

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Job Feeds"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


def _meta_description(job) -> str:
    source = (job.description or f"Apply for {job.title}").replace("\n", " ").strip()
    return source[:155]


def _job_lastmod(job) -> str | None:
    lastmod = job.updated_at or job.created_at
    if lastmod is None:
        return None
    return lastmod.date().isoformat()


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


@router.get("/jobs/{job_reference}", response_class=HTMLResponse)
def public_job_detail(request: Request, job_reference: str, db: Session = Depends(get_db)):
    job = get_public_job_by_reference_or_404(db, job_reference)
    canonical_path = get_job_canonical_path(job)
    if request.url.path != canonical_path:
        return RedirectResponse(url=canonical_path, status_code=status.HTTP_308_PERMANENT_REDIRECT)

    skills = normalize_skills(job.skills)
    canonical_url = build_public_job_url(job)
    apply_url = build_public_apply_url(job)
    schema = build_job_posting_schema(
        job,
        job_url=canonical_url,
        applicant_location=job.country or None,
    )
    return templates.TemplateResponse(
        "jobs/detail.html",
        {
            "request": request,
            "job": job,
            "location": build_location(job),
            "skills": skills,
            "apply_url": apply_url,
            "canonical_url": canonical_url,
            "page_title": f"{job.title} at {job.company_name or 'Company'}",
            "meta_description": _meta_description(job),
            "job_posting_schema_json": dump_job_posting_schema(schema),
        },
    )


@router.post("/jobs/{job_reference}/apply", response_model=JobApplicationResponse, status_code=status.HTTP_201_CREATED)
async def apply_to_job(
    job_reference: str,
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    phone: str | None = Form(None),
    cover_letter: str | None = Form(None),
    resume: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    job = get_public_job_by_reference_or_404(db, job_reference)
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
                f"<p><a href='{get_job_canonical_path(job)}' style='color:#0f766e;'>Return to job page</a></p>"
                "</main></body></html>"
            ),
        )

    return application


@router.get("/sitemap.xml")
def sitemap_xml(db: Session = Depends(get_db)):
    jobs = JobDistributionService.list_active_jobs(db)
    root = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")

    for job in jobs:
        url = ET.SubElement(root, "url")
        append_text_element(url, "loc", build_public_job_url(job))
        append_text_element(url, "lastmod", _job_lastmod(job))

    xml_content = prettify_xml(root)
    return Response(
        content=xml_content,
        media_type="application/xml; charset=utf-8",
        headers={"Content-Type": "application/xml; charset=utf-8"},
    )


@router.get("/robots.txt")
def robots_txt():
    return PlainTextResponse(
        "\n".join(
            [
                "User-agent: Googlebot",
                "Allow: /",
                "",
                "User-agent: Googlebot-Image",
                "Allow: /",
                "",
                "User-agent: AdsBot-Google",
                "Allow: /",
                "",
                "User-agent: *",
                "Allow: /",
                "",
                "Sitemap: https://pontis.one/sitemap.xml",
            ]
        )
    )
