from app.runners.record_runner import ensure_record_output
import json
import re
import traceback
from pathlib import Path

from app.adapters.record_adapter import convert_record_output
from app.schemas.content import ContentDocument
from app.orchestrator.job_manager import (
    init_db,
    claim_next_job,
    finish_job,
)

BASE_DIR = Path(__file__).resolve().parents[2]
INPUT_DIR = BASE_DIR / "data" / "inputs"
RESULT_DIR = BASE_DIR / "data" / "results"


def process_job(job):
    material_id = job["material_id"]

    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", material_id):
        raise ValueError("Invalid material ID")

    if job["source_type"] not in ("audio", "video"):
        raise NotImplementedError("PDF adapter not connected yet")

    if set(job["tasks"]) - {"quiz", "microcontent"}:
        raise NotImplementedError("Requested task not supported yet")


    # Tự chạy Record-to-Quiz nếu chưa có JSON đầu ra.
    input_path = ensure_record_output(
        material_id=material_id,
        source_type=job["source_type"],
    )

    raw = json.loads(
        input_path.read_text(encoding="utf-8-sig")
    )


    result = convert_record_output(
        raw,
        material_id=material_id,
        source_type=job["source_type"],
    )

    # Kiểm tra nội dung đã chuẩn hóa.
    ContentDocument.model_validate(result["document"])

    if "quiz" in job["tasks"] and not result["generated"]["questions"]:
        raise ValueError("No quiz questions generated")

    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    result_path = RESULT_DIR / f"{job['job_id']}.json"
    temp_path = RESULT_DIR / f"{job['job_id']}.tmp"

    temp_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(result_path)

    print(f"Saved result: {result_path}")


def run_once():
    init_db()
    job = claim_next_job()

    if job is None:
        print("No queued jobs")
        return

    print(f"Processing job: {job['job_id']}")

    try:
        process_job(job)
    except Exception:
        traceback.print_exc()
        finish_job(job["job_id"], "failed")
        return

    finish_job(job["job_id"], "completed")
    print("Job completed successfully")


if __name__ == "__main__":
    run_once()
