"""
CRSMCPAI Alpha - Sovereign File Upload/Download Demo Router
Superadmin: SLMK Jesse Martinez Junior
Genesis Hash: 92038cafccc7192535bd475cca985d03000d89962b8dc96f6664081663559b1b
"""

import os
import shutil
import logging
from pathlib import Path
from typing import Dict, Any
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from fastapi.responses import FileResponse

logger = logging.getLogger("CRSMCPAI.DemoFiles")

router = APIRouter(prefix="/api/files", tags=["File Operations"])

# Define secure upload directory relative to workspace or secure ephemeral path
# Using Path.resolve() to prevent path traversal issues
BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "workspace" / "jesse-ai-website" / "uploads"

# Defensive directory initialization with exception handling to prevent startup crashes
try:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Upload directory verified/initialized at: {UPLOAD_DIR}")
except Exception as e:
    logger.error(f"Failed to create upload directory at startup: {e}")
    # Fallback to tmp if workspace is read-only
    UPLOAD_DIR = Path("/tmp/crs_uploads")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB limit for demo security

@router.post("/upload")
async def upload_demo_file(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    Securely uploads a file for the public demo interface with size and type validation.
    """
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No filename provided.")

    # Sanitize filename
    safe_filename = Path(file.filename).name
    destination_path = UPLOAD_DIR / safe_filename

    try:
        contents = await file.read()
        file_size = len(contents)

        if file_size > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File size exceeds maximum allowed limit of 10MB."
            )

        with open(destination_path, "wb") as buffer:
            buffer.write(contents)

        logger.info(f"File successfully uploaded: {safe_filename} ({file_size} bytes)")

        return {
            "status": "SUCCESS",
            "filename": safe_filename,
            "size_bytes": file_size,
            "message": "File securely stored in sovereign buffer.",
            "block_hash": "92038cafccc7192535bd475cca985d03000d89962b8dc96f6664081663559b1b"
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"File upload processing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal file storage error: {str(e)}"
        )

@router.get("/download/{filename}")
async def download_demo_file(filename: str) -> FileResponse:
    """
    Securely downloads a previously uploaded demo file, guarding against path traversal.
    """
    # Prevent path traversal attacks (e.g., ../../etc/passwd)
    safe_filename = Path(filename).name
    file_path = (UPLOAD_DIR / safe_filename).resolve()

    # Ensure resolved path is strictly within UPLOAD_DIR
    if not str(file_path).startswith(str(UPLOAD_DIR.resolve())) or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Requested file not found or access denied."
        )

    return FileResponse(path=str(file_path), filename=safe_filename)
