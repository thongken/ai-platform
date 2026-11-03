
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.materials import router as materials_router
from app.schemas.content import ContentDocument
from app.api.jobs import router as jobs_router
from app.orchestrator.job_manager import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="AI Microlearning Platform",
    description="Central AI Backend for Moodle LMS",
    version="0.2.0",
    lifespan=lifespan
)

app.include_router(jobs_router)
app.include_router(materials_router)


@app.get("/")
def home():
    return {
        "message": "AI Microlearning Platform",
        "status": "running"
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "ai-platform"
    }


@app.post("/api/v1/content/validate")
def validate_content(document: ContentDocument):
    return {
        "valid": True,
        "material_id": document.material_id,
        "source_type": document.source_type,
        "sections_count": len(document.sections),
        "message": "Content schema is valid"
    }
