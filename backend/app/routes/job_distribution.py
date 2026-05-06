from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session
from uuid import UUID

from app.api.deps import get_db
from app.schemas import ATSJobCreate, ATSJobDetailResponse, ATSJobListResponse, ATSJobResponse, ATSJobUpdate
from app.services.jobs import JobDistributionService

router = APIRouter(prefix="/distribution/jobs", tags=["Job Distribution"])


@router.post("", response_model=ATSJobResponse, status_code=status.HTTP_201_CREATED)
def create_distribution_job(payload: ATSJobCreate, db: Session = Depends(get_db)):
    return JobDistributionService.create_job(db, payload)


@router.get("", response_model=ATSJobListResponse)
def list_distribution_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    location: str | None = None,
    skills: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
):
    return JobDistributionService.list_jobs(
        db,
        page=page,
        page_size=page_size,
        search=search,
        location=location,
        skills=skills,
        status_filter=status_filter,
    )


@router.get("/{job_id}", response_model=ATSJobDetailResponse)
def get_distribution_job(job_id: UUID, db: Session = Depends(get_db)):
    return JobDistributionService.get_public_job_detail(db, job_id)


@router.put("/{job_id}", response_model=ATSJobResponse)
def update_distribution_job(
    job_id: UUID,
    payload: ATSJobUpdate,
    db: Session = Depends(get_db),
):
    return JobDistributionService.update_job(db, job_id, payload)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_distribution_job(job_id: UUID, db: Session = Depends(get_db)):
    JobDistributionService.delete_job(db, job_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
