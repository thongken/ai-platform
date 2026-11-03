from typing import Literal
from pydantic import BaseModel, Field


SourceType = Literal["audio", "video", "pdf"]

TaskType = Literal[
    "quiz",
    "microcontent",
    "slides",
    "tts"
]

JobStatus = Literal[
    "queued",
    "running",
    "completed",
    "failed"
]


class CreateJobRequest(BaseModel):
    material_id: str = Field(min_length=1)
    source_type: SourceType
    tasks: list[TaskType] = Field(min_length=1)


class JobResponse(CreateJobRequest):
    job_id: str
    status: JobStatus
    created_at: str
