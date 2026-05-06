from __future__ import annotations

import re
import uuid
from pathlib import Path

import aiofiles
from fastapi import HTTPException, UploadFile, status

from app.core.configuration import settings


RESUME_UPLOAD_SUBDIR = "resumes"
ALLOWED_RESUME_EXTENSIONS = {".pdf", ".doc", ".docx"}
ALLOWED_RESUME_CONTENT_TYPES = {
    ".pdf": {"application/pdf"},
    ".doc": {"application/msword", "application/octet-stream"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
        "application/octet-stream",
    },
}
CHUNK_SIZE = 1024 * 1024


def get_resume_upload_dir() -> Path:
    return Path(settings.UPLOAD_DIR).resolve() / RESUME_UPLOAD_SUBDIR


def ensure_resume_upload_dir() -> Path:
    upload_dir = get_resume_upload_dir()
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def _sanitize_original_filename(filename: str | None) -> str:
    safe_name = Path(filename or "resume").name
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", safe_name).strip("._")
    return safe_name or "resume"


def _validate_resume_extension(filename: str) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_RESUME_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid resume file type. Allowed types: pdf, doc, docx.",
        )
    return extension


def _validate_resume_content_type(extension: str, content_type: str | None) -> None:
    if not content_type:
        return
    allowed_types = ALLOWED_RESUME_CONTENT_TYPES.get(extension, set())
    if allowed_types and content_type.lower() not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume content type does not match the uploaded file extension.",
        )


async def save_resume_upload(upload: UploadFile) -> dict[str, str]:
    original_filename = _sanitize_original_filename(upload.filename)
    extension = _validate_resume_extension(original_filename)
    _validate_resume_content_type(extension, upload.content_type)

    upload_dir = ensure_resume_upload_dir()
    stored_filename = f"{uuid.uuid4()}_resume{extension}"
    destination = (upload_dir / stored_filename).resolve()
    upload_root = upload_dir.resolve()
    if upload_root not in destination.parents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid upload destination.")

    total_bytes = 0
    try:
        async with aiofiles.open(destination, "wb") as output_file:
            while True:
                chunk = await upload.read(CHUNK_SIZE)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > settings.RESUME_UPLOAD_MAX_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Resume file exceeds the 5MB upload limit.",
                    )
                await output_file.write(chunk)
    except Exception:
        if destination.exists():
            destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()

    if total_bytes == 0:
        destination.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded resume file is empty.",
        )

    relative_url = f"/uploads/{RESUME_UPLOAD_SUBDIR}/{stored_filename}"
    public_base = settings.PUBLIC_BASE_URL.rstrip("/")
    return {
        "original_filename": original_filename,
        "stored_filename": stored_filename,
        "resume_url": f"{public_base}{relative_url}",
        "stored_path": str(destination),
        "size_bytes": str(total_bytes),
    }
