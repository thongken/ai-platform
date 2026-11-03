import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile


router = APIRouter(
    prefix="/api/v1/materials",
    tags=["Materials"]
)

BASE_DIR = Path(__file__).resolve().parents[2]
UPLOAD_DIR = BASE_DIR / "data" / "uploads"

ALLOWED_TYPES = {
    ".mp3": "audio",
    ".wav": "audio",
    ".m4a": "audio",
    ".mp4": "video",
    ".pdf": "pdf",
}

MAX_SIZE = 200 * 1024 * 1024  # 200 MB


@router.post("/upload", status_code=201)
async def upload_material(file: UploadFile = File(...)):
    filename = file.filename or ""
    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type"
        )

    material_id = f"mat_{uuid4().hex}"
    source_type = ALLOWED_TYPES[extension]

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    saved_filename = f"{material_id}{extension}"
    file_path = UPLOAD_DIR / saved_filename
    metadata_path = UPLOAD_DIR / f"{material_id}.json"

    size = 0

    try:
        with file_path.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)

                if size > MAX_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail="File exceeds 200 MB"
                    )

                output.write(chunk)

        if size == 0:
            raise HTTPException(
                status_code=400,
                detail="Empty file"
            )

        metadata = {
            "material_id": material_id,
            "original_filename": filename,
            "saved_filename": saved_filename,
            "source_type": source_type,
            "size_bytes": size,
            "created_at": datetime.now(
                timezone.utc
            ).isoformat()
        }

        metadata_path.write_text(
            json.dumps(
                metadata,
                ensure_ascii=False,
                indent=2
            ),
            encoding="utf-8"
        )

    except Exception:
        file_path.unlink(missing_ok=True)
        metadata_path.unlink(missing_ok=True)
        raise

    finally:
        await file.close()

    return {
        "status": "uploaded",
        "material_id": material_id,
        "source_type": source_type,
        "filename": filename,
        "size_bytes": size
    }
