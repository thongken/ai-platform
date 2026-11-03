# AI Platform

Backend FastAPI quản lý tác vụ AI cho LMS: nhận tài liệu, lưu hàng đợi bằng SQLite, gọi Record-to-Quiz và chuẩn hóa kết quả thành nội dung học tập, câu hỏi trắc nghiệm.

## Chức năng hiện có

- Upload audio/video/PDF, tối đa 200 MB mỗi file.
- Tạo job, xem trạng thái và lấy kết quả qua API.
- Worker xử lý **audio/video** với tác vụ `quiz`, `microcontent`; gọi Record-to-Quiz qua WSL khi chưa có JSON đầu ra hợp lệ.
- Kết quả gồm transcript, các section kèm mốc thời gian, tóm tắt và câu hỏi. Nội dung section lấy từ `segment_summary`.

**Giới hạn:** API/schema nhận `pdf`, `slides`, `tts`, nhưng worker chưa hỗ trợ xử lý các loại này. Mỗi lần chạy worker chỉ lấy **một job** rồi thoát; không tự theo dõi hàng đợi liên tục. Worker hiện tạo cùng bộ kết quả chuẩn hóa cho `quiz` và `microcontent`.

## Cấu trúc thư mục

```text
ai-platform/
├── app/
│   ├── main.py                    # FastAPI, health check, validate nội dung
│   ├── api/
│   │   ├── materials.py           # Upload và lưu metadata
│   │   └── jobs.py                # Tạo job, xem trạng thái/kết quả
│   ├── schemas/
│   │   ├── content.py             # Schema tài liệu, section, vị trí nguồn
│   │   └── jobs.py                # Schema job, loại nguồn và tác vụ
│   ├── orchestrator/
│   │   └── job_manager.py         # SQLite, nhận và cập nhật job
│   ├── runners/
│   │   ├── __init__.py
│   │   └── record_runner.py       # Gọi PHP CLI Record-to-Quiz qua WSL
│   ├── adapters/
│   │   └── record_adapter.py      # Chuyển JSON Record-to-Quiz sang schema chung
│   └── workers/
│       └── worker.py              # Xử lý một job đang chờ
├── data/                          # Dữ liệu local, không commit
│   ├── jobs.sqlite3               # Hàng đợi và trạng thái job
│   ├── uploads/                   # File upload và metadata JSON
│   ├── inputs/                    # JSON đầu ra gốc từ Record-to-Quiz
│   ├── results/                   # Kết quả chuẩn hóa theo job_id
│   └── record_normalized.json     # Đầu ra mặc định khi chạy adapter riêng
├── .venv/                         # Môi trường Python local, không commit
├── run-worker.ps1                 # Khởi chạy worker trên PowerShell
├── .gitignore
└── README.md
```

Các thư mục dữ liệu cần thiết và database được tạo khi chạy API/worker; `record_normalized.json` chỉ được tạo khi chạy adapter riêng với đường dẫn đầu ra mặc định.

## Cài đặt

Chạy các lệnh PowerShell tại thư mục `ai-platform`. Mã nguồn dùng cú pháp Python 3.10+ và Pydantic 2; môi trường local hiện dùng Python 3.13. Dự án chưa có `requirements.txt` hoặc `pyproject.toml`, nên cài trực tiếp các thư viện đang dùng:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install fastapi uvicorn "pydantic>=2" python-multipart
```

Để xử lý file mới, runner yêu cầu:

- Windows có WSL và PHP CLI trong WSL.
- Record-to-Quiz đã cài dependency, nằm đúng đường dẫn cố định `../record-to-quiz/php-service/bin/record-to-quiz.php`, tính từ `ai-platform`.
- Dịch vụ Whisper và Gemini API key được cấu hình cho pipeline Record-to-Quiz.

Runner dùng lại `data/inputs/<material_id>.json` nếu file chứa kết quả hợp lệ; trường hợp này không gọi pipeline bên ngoài.

## Khởi chạy và sử dụng

### 1. Chạy API

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8002 --reload
```

Kiểm tra tại `http://127.0.0.1:8002/health`; Swagger UI tại `http://127.0.0.1:8002/docs`. Cổng `8002` trong ví dụ dành cho API này để tách khỏi Whisper mặc định ở cổng `8000`.

| Method | Endpoint | Chức năng |
|---|---|---|
| GET | `/` | Thông tin dịch vụ |
| GET | `/health` | Kiểm tra API đang chạy |
| POST | `/api/v1/materials/upload` | Upload trường multipart `file`; nhận `material_id` |
| POST | `/api/v1/jobs` | Tạo job, trả HTTP 202 |
| GET | `/api/v1/jobs/{job_id}` | Xem trạng thái job |
| GET | `/api/v1/jobs/{job_id}/result` | Lấy JSON kết quả; trả 409 nếu job chưa hoàn thành |
| POST | `/api/v1/content/validate` | Kiểm tra JSON theo schema `ContentDocument` |

### 2. Upload và tạo job

Mở terminal PowerShell khác tại `ai-platform`, thay đường dẫn file trong ví dụ bằng file thực tế:

```powershell
$baseUrl = "http://127.0.0.1:8002"
$upload = curl.exe --fail-with-body -sS -F "file=@C:\path\lesson.mp4" "$baseUrl/api/v1/materials/upload" | ConvertFrom-Json
$body = @{
    material_id = $upload.material_id
    source_type = $upload.source_type
    tasks = @("quiz", "microcontent")
} | ConvertTo-Json
$job = Invoke-RestMethod -Method Post -Uri "$baseUrl/api/v1/jobs" -ContentType "application/json" -Body $body
$job
```

Upload hỗ trợ `.mp3`, `.wav`, `.m4a`, `.mp4`, `.pdf`; để chạy worker hiện tại, chọn audio hoặc video. Upload chỉ lưu file và metadata, chưa tạo job.

### 3. Chạy worker và lấy kết quả

Trong terminal vừa tạo job:

```powershell
.\run-worker.ps1
Invoke-RestMethod "$baseUrl/api/v1/jobs/$($job.job_id)"
Invoke-RestMethod "$baseUrl/api/v1/jobs/$($job.job_id)/result"
```

Script dùng Python trong `.venv`, hỏi Gemini API key nếu biến `GEMINI_API_KEY` chưa có. Không cần kích hoạt virtual environment trước khi chạy script.

| Biến môi trường | Cấu hình hiện tại |
|---|---|
| `GEMINI_API_KEY` | Script đọc từ môi trường hoặc yêu cầu nhập ẩn trong terminal |
| `WHISPER_URL` | Script luôn đặt `http://127.0.0.1:8000` |
| `GEMINI_MODEL` | Script luôn đặt `gemini-3.5-flash-lite`; runner dùng mặc định `gemini-3.1-flash-lite` nếu biến chưa được đặt |

Các giá trị trên được lấy từ mã nguồn, cần phù hợp dịch vụ và quyền truy cập thực tế. Muốn tự cấu hình `WHISPER_URL` hoặc `GEMINI_MODEL`, đặt biến trong PowerShell rồi chạy trực tiếp `.\.venv\Scripts\python.exe -m app.workers.worker`; `run-worker.ps1` sẽ ghi đè hai biến này. Mã nguồn hiện không tự đọc file `.env`.

Luồng trạng thái: `queued` → `running` → `completed` hoặc `failed`. Kết quả lưu tại `data/results/<job_id>.json`. Nếu còn job chờ, chạy lại worker; `No queued jobs` nghĩa là không có job ở trạng thái `queued`.

## Xử lý lỗi

| Hiện tượng | Kiểm tra |
|---|---|
| `ModuleNotFoundError` | Cài các thư viện vào đúng `.venv` và dùng Python trong `.venv` |
| PowerShell chặn `.ps1` | Nếu chính sách máy cho phép, chạy `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` trong terminal hiện tại |
| `Record-to-Quiz CLI not found` | Kiểm tra đường dẫn `../record-to-quiz/php-service/bin/record-to-quiz.php` |
| `Expected one uploaded file` | Kiểm tra `material_id`, `source_type` và file tương ứng trong `data/uploads/` |
| Job `failed` | Đọc traceback ở terminal worker; kiểm tra WSL/PHP, Whisper, Gemini và loại tác vụ |
| Lấy kết quả trả 409 | Kiểm tra trạng thái job; chỉ job `completed` mới lấy được kết quả |

## File nên lưu trong Git

Giữ mã nguồn `app/`, `run-worker.ps1`, `README.md`, `.gitignore` và các file khai báo dependency/cấu hình mẫu khi bổ sung. Bỏ qua `.venv/`, `__pycache__/`, toàn bộ dữ liệu runtime trong `data/`, log, file tạm và cấu hình chứa secret theo [`.gitignore`](.gitignore).

Không ghi API key vào mã nguồn hoặc tài liệu. `.gitignore` chỉ ngăn thêm file mới; file đã được Git theo dõi cần bỏ theo dõi riêng nếu muốn loại khỏi repository.
