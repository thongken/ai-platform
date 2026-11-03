import json
import os
import re
import subprocess
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]

RECORD_DIR = BASE_DIR.parent / "record-to-quiz" / "php-service"
UPLOAD_DIR = BASE_DIR / "data" / "uploads"
INPUT_DIR = BASE_DIR / "data" / "inputs"

EXTENSIONS = {
    "audio": [".mp3", ".wav", ".m4a"],
    "video": [".mp4"],
}


def to_wsl_path(path: Path) -> str:
    """Chuyển đường dẫn Windows thành đường dẫn WSL."""

    result = subprocess.run(
        [
            "wsl.exe",
            "--exec",
            "wslpath",
            "-u",
            str(path.resolve()),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    return result.stdout.strip()


def valid_output(path: Path) -> bool:
    """Kiểm tra JSON gốc đã có Quiz thành công chưa."""

    try:
        data = json.loads(
            path.read_text(encoding="utf-8-sig")
        )

        results = data.get("results", [])

        return (
            isinstance(results, list)
            and len(results) == 1
            and isinstance(results[0].get("quiz"), dict)
            and not results[0].get("error")
        )

    except (OSError, ValueError, AttributeError, TypeError):
        return False


def ensure_record_output(
    material_id: str,
    source_type: str,
) -> Path:
    """
    Nếu JSON thành công đã có thì dùng lại.
    Nếu chưa có thì chạy Record-to-Quiz thật.
    """

    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", material_id):
        raise ValueError("Invalid material ID")

    if source_type not in EXTENSIONS:
        raise ValueError("Unsupported record source type")

    INPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_path = INPUT_DIR / f"{material_id}.json"

    if output_path.is_file() and valid_output(output_path):
        print("Using existing Record-to-Quiz output")
        return output_path

    candidates = [
        UPLOAD_DIR / f"{material_id}{ext}"
        for ext in EXTENSIONS[source_type]
    ]

    uploads = [p for p in candidates if p.is_file()]

    if len(uploads) != 1:
        raise FileNotFoundError(
            f"Expected one uploaded file for {material_id}"
        )

    if not (RECORD_DIR / "bin" / "record-to-quiz.php").is_file():
        raise FileNotFoundError(
            f"Record-to-Quiz CLI not found: {RECORD_DIR}"
        )

    env = os.environ.copy()

    if not env.get("GEMINI_API_KEY"):
        raise RuntimeError(
            "GEMINI_API_KEY missing in Windows Worker environment"
        )

    env.setdefault("WHISPER_URL", "http://127.0.0.1:8000")
    env.setdefault("GEMINI_MODEL", "gemini-3.1-flash-lite")

    # Truyền biến môi trường từ Windows sang WSL.
    entries = [
        entry for entry in env.get("WSLENV", "").split(":")
        if entry
    ]

    for name in ("GEMINI_API_KEY", "WHISPER_URL", "GEMINI_MODEL"):
        if not any(e.split("/")[0] == name for e in entries):
            entries.append(f"{name}/u")

    env["WSLENV"] = ":".join(entries)

    # Chuyển đường dẫn Windows → Ubuntu WSL.
    repo_wsl = to_wsl_path(RECORD_DIR)
    input_wsl = to_wsl_path(uploads[0])
    output_wsl = to_wsl_path(output_path)

    # Loại bỏ kết quả lỗi cũ trước khi chạy lại.
    output_path.unlink(missing_ok=True)

    print(f"Running Record-to-Quiz for {material_id}")

    result = subprocess.run(
        [
            "wsl.exe",
            "--exec",
            "bash",
            "-lc",
            'cd "$1" && php bin/record-to-quiz.php "$2" --output "$3"',
            "record-runner",
            repo_wsl,
            input_wsl,
            output_wsl,
        ],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=1800,
    )

    if output_path.is_file():
        try:
            raw = json.loads(
                output_path.read_text(encoding="utf-8-sig")
            )
            records = raw.get("results", [])

            if records and records[0].get("error"):
                raise RuntimeError(records[0]["error"])

        except json.JSONDecodeError as exc:
            raise RuntimeError("Invalid pipeline JSON") from exc

    if result.returncode != 0:
        raise RuntimeError(
            f"Record-to-Quiz exited with {result.returncode}: "
            + (result.stderr or result.stdout)[-1000:]
        )

    if not output_path.is_file() or not valid_output(output_path):
        raise RuntimeError(
            "Record-to-Quiz did not produce a valid quiz JSON"
        )

    print("Record-to-Quiz pipeline completed")

    return output_path
