import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas import ATSJobDetailResponse
from app.services.feeds import feed_registry
from app.services.jobs import JobDistributionService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Job Feeds"])


def _build_feed_response(db: Session, portal_name: str) -> Response:
    jobs = JobDistributionService.list_active_jobs(db)

    try:
        xml_content = feed_registry.get(portal_name).build_feed(jobs)
        JobDistributionService.mark_jobs_as_published(db, portal_name, jobs)
        return Response(content=xml_content, media_type="application/xml")
    except Exception as exc:
        logger.exception("Failed to generate %s feed", portal_name)
        JobDistributionService.mark_feed_failure(db, portal_name, str(exc))
        raise HTTPException(status_code=500, detail=f"Failed to generate {portal_name} feed")


@router.get("/jobs-feed.xml")
def default_jobs_feed(db: Session = Depends(get_db)):
    return _build_feed_response(db, "default")


@router.get("/feeds/jooble.xml")
def jooble_feed(db: Session = Depends(get_db)):
    return _build_feed_response(db, "jooble")


@router.get("/feeds/careerjet.xml")
def careerjet_feed(db: Session = Depends(get_db)):
    return _build_feed_response(db, "careerjet")


@router.get("/feeds/talent.xml")
def talent_feed(db: Session = Depends(get_db)):
    return _build_feed_response(db, "talent")


@router.get("/jobs/{job_id}", response_model=ATSJobDetailResponse)
def public_job_detail(job_id: UUID, db: Session = Depends(get_db)):
    return JobDistributionService.get_public_job_detail(db, job_id)
