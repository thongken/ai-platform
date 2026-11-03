
# Chuyển đến thư mục AI Platform
Set-Location $PSScriptRoot

# Đường dẫn Python trong môi trường ảo
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Error "Khong tim thay Python .venv"
    exit 1
}

# Nhập Gemini API key nếu chưa có
if (-not $env:GEMINI_API_KEY) {
    $secureKey = Read-Host "Nhap Gemini API key" -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)

    try {
        $env:GEMINI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
    }
}

# Cau hinh AI Services
$env:WHISPER_URL = "http://127.0.0.1:8000"
$env:GEMINI_MODEL = "gemini-3.5-flash-lite"

# Chay Worker
Write-Host "Dang chay AI Worker..." -ForegroundColor Cyan

& $python -m app.workers.worker
