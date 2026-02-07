from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth import get_current_active_user
from app.models import User
from pydantic import BaseModel

router = APIRouter(prefix="/settings", tags=["Settings"])

class ResumeScoreSettings(BaseModel):
    minPassingScore: int

# In-memory storage for demo - in production, use database
_settings_store = {"minPassingScore": 70}

@router.get("/resume-score")
def get_resume_score_settings(
    current_user: User = Depends(get_current_active_user)
):
    return _settings_store

@router.post("/resume-score")
def save_resume_score_settings(
    settings: ResumeScoreSettings,
    current_user: User = Depends(get_current_active_user)
):
    _settings_store["minPassingScore"] = settings.minPassingScore
    return {"message": "Settings saved successfully"}