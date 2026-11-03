import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.schemas.jobs import CreateJobRequest


BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BASE_DIR / "data" / "jobs.sqlite3"


def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with closing(connect_db()) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                material_id TEXT NOT NULL,
                source_type TEXT NOT NULL,
                tasks TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()


def create_job(request: CreateJobRequest):
    job_id = str(uuid4())
    created_at = datetime.now(
        timezone.utc
    ).isoformat()

    with closing(connect_db()) as conn:
        conn.execute("""
            INSERT INTO jobs (
                job_id, material_id, source_type,
                tasks, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            job_id,
            request.material_id,
            request.source_type,
            json.dumps(request.tasks),
            "queued",
            created_at
        ))
        conn.commit()

    return get_job(job_id)


def get_job(job_id: str):
    with closing(connect_db()) as conn:
        row = conn.execute(
            "SELECT * FROM jobs WHERE job_id = ?",
            (job_id,)
        ).fetchone()

    if row is None:
        return None

    job = dict(row)
    job["tasks"] = json.loads(job["tasks"])

    return job

def claim_next_job():
    """Lấy một Job đang chờ và chuyển sang running."""

    with closing(connect_db()) as conn:
        try:
            conn.execute("BEGIN IMMEDIATE")

            row = conn.execute("""
                SELECT job_id
                FROM jobs
                WHERE status = 'queued'
                ORDER BY created_at, job_id
                LIMIT 1
            """).fetchone()

            if row is None:
                conn.commit()
                return None

            job_id = row["job_id"]

            conn.execute("""
                UPDATE jobs
                SET status = 'running'
                WHERE job_id = ?
            """, (job_id,))

            conn.commit()

        except Exception:
            conn.rollback()
            raise

    return get_job(job_id)


def finish_job(job_id: str, status: str):
    """Đánh dấu Job đã hoàn thành hoặc thất bại."""

    if status not in ("completed", "failed"):
        raise ValueError("Invalid final status")

    with closing(connect_db()) as conn:
        cursor = conn.execute("""
            UPDATE jobs
            SET status = ?
            WHERE job_id = ?
              AND status = 'running'
        """, (status, job_id))

        conn.commit()

        if cursor.rowcount != 1:
            raise RuntimeError("Job is not running")

    return get_job(job_id)
