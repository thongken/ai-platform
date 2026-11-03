from fastapi import APIRouter, HTTPException
import json
from pathlib import Path
from uuid import UUID
from app.schemas.jobs import (
    CreateJobRequest,
    JobResponse
)

from app.orchestrator.job_manager import (
    create_job,
    get_job
)


router = APIRouter(
    prefix="/api/v1/jobs",
    tags=["AI Jobs"]
)


@router.post(
    "",
    response_model=JobResponse,
    status_code=202
)
def submit_job(request: CreateJobRequest):
    return create_job(request)


@router.get(
    "/{job_id}",
    response_model=JobResponse
)
def read_job(job_id: str):
    job = get_job(job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found"
        )

    return job

RESULT_DIR = Path(__file__).resolve().parents[2] / "data" / "results"


@router.get("/{job_id}/result")
def read_job_result(job_id: UUID):
    job = get_job(str(job_id))

    if job is None:
        raise HTTPException(404, "Job not found")

    if job["status"] != "completed":
        raise HTTPException(
            409, "Job has not completed"
        )

    result_path = RESULT_DIR / f"{job_id}.json"

    if not result_path.is_file():
        raise HTTPException(404, "Result file not found")

    return json.loads(
        result_path.read_text(encoding="utf-8")
    )
