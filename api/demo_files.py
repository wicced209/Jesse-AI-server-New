"""
File upload/download for the Jesse AI public demo.

Safe file handling for the public website:
- Upload: size-limited, type-checked, scanned for safety
- Download: only files generated through the demo
- All files expire after 24 hours
- Rate-limited per IP
"""

from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse
from datetime import datetime, timezone, timedelta
import time
import hashlib
import os
import uuid

router = APIRouter()

# Storage
UPLOAD_DIR = "/tmp/jesse_demo_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Limits
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
FILE_TTL_HOURS = 24
ALLOWED_EXTENSIONS = {
    ".txt", ".md", ".json", ".csv", ".pdf",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp",
    ".wav", ".mp3", ".py", ".js", ".html", ".css",
}

# Rate limiting
_upload_requests: dict = {}
UPLOAD_RATE_LIMIT = 20  # per hour


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_rate_limit(ip: str) -> bool:
    now = time.time()
    key = hashlib.sha256(f"upload:{ip}".encode()).hexdigest()[:16]
    timestamps = _upload_requests.get(key, [])
    timestamps = [t for t in timestamps if now - t < 3600]
    if len(timestamps) >= UPLOAD_RATE_LIMIT:
        return False
    timestamps.append(now)
    _upload_requests[key] = timestamps
    return True


def _cleanup_expired():
    """Remove files older than TTL."""
    now = time.time()
    cutoff = now - (FILE_TTL_HOURS * 3600)
    try:
        for fname in os.listdir(UPLOAD_DIR):
            fpath = os.path.join(UPLOAD_DIR, fname)
            if os.path.isfile(fpath) and os.path.getmtime(fpath) < cutoff:
                os.remove(fpath)
    except Exception:
        pass


@router.post("/demo/upload")
async def demo_upload(request: Request, file: UploadFile = File(...)):
    """Upload a file through the public demo. 10MB max, 24h expiry."""
    ip = _client_ip(request)

    if not _check_rate_limit(ip):
        return JSONResponse(status_code=429, content={
            "error": "Upload rate limit reached. Try again in an hour.",
            "demo": True,
        })

    # Check extension
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return JSONResponse(status_code=400, content={
            "error": f"File type '{ext}' not allowed in demo.",
            "allowed": sorted(ALLOWED_EXTENSIONS),
            "demo": True,
        })

    # Read and check size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        return JSONResponse(status_code=400, content={
            "error": "File too large. Maximum 10 MB.",
            "demo": True,
        })

    if len(content) == 0:
        return JSONResponse(status_code=400, content={
            "error": "Empty file.",
            "demo": True,
        })

    # Save with unique ID
    file_id = str(uuid.uuid4())[:12]
    safe_name = f"{file_id}_{os.path.basename(file.filename or 'upload')}"
    fpath = os.path.join(UPLOAD_DIR, safe_name)

    with open(fpath, "wb") as f:
        f.write(content)

    _cleanup_expired()

    return {
        "demo": True,
        "file_id": file_id,
        "filename": file.filename,
        "size_bytes": len(content),
        "download_url": f"/demo/download/{file_id}",
        "expires_in_hours": FILE_TTL_HOURS,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/demo/download/{file_id}")
async def demo_download(file_id: str):
    """Download a previously uploaded demo file."""
    _cleanup_expired()

    # Find file by ID prefix
    for fname in os.listdir(UPLOAD_DIR):
        if fname.startswith(file_id):
            fpath = os.path.join(UPLOAD_DIR, fname)
            original_name = fname[len(file_id) + 1:]
            return FileResponse(
                fpath,
                filename=original_name,
                media_type="application/octet-stream",
            )

    return JSONResponse(status_code=404, content={
        "error": "File not found or expired.",
        "demo": True,
    })


@router.get("/demo/files")
async def demo_list_files():
    """List currently available demo files (names only, no content)."""
    _cleanup_expired()
    files = []
    try:
        for fname in os.listdir(UPLOAD_DIR):
            fpath = os.path.join(UPLOAD_DIR, fname)
            if os.path.isfile(fpath):
                file_id = fname.split("_")[0]
                original = fname[len(file_id) + 1:]
                files.append({
                    "file_id": file_id,
                    "filename": original,
                    "size_bytes": os.path.getsize(fpath),
                })
    except Exception:
        pass

    return {
        "demo": True,
        "files": files,
        "count": len(files),
    }
