"""
Public demo endpoint for the Jesse AI website.

Rate-limited, safe subset of /command for public visitors.
- 10 requests per hour per IP
- No admin functions
- No memory writes to Jesse's private conversation store
- All demo commands logged to a separate demo ledger
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import datetime, timezone
import time
import hashlib

router = APIRouter()

# Rate limiting: IP -> list of timestamps
_demo_requests: dict = {}
DEMO_RATE_LIMIT = 10  # requests
DEMO_WINDOW_SECONDS = 3600  # per hour

# Blocked patterns for demo (safety)
BLOCKED_PATTERNS = [
    "admin", "superadmin", "password", "token", "secret",
    "delete", "drop", "shutdown", "reboot", "exec(",
    "import os", "import sys", "subprocess",
]


class DemoRequest(BaseModel):
    command: str
    use_llm: bool = True


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_rate_limit(ip: str) -> bool:
    now = time.time()
    key = hashlib.sha256(ip.encode()).hexdigest()[:16]
    timestamps = _demo_requests.get(key, [])
    timestamps = [t for t in timestamps if now - t < DEMO_WINDOW_SECONDS]
    if len(timestamps) >= DEMO_RATE_LIMIT:
        return False
    timestamps.append(now)
    _demo_requests[key] = timestamps
    return True


def _is_safe(command: str) -> tuple:
    lower = command.lower()
    for pattern in BLOCKED_PATTERNS:
        if pattern in lower:
            return False, f"Demo does not support '{pattern}' commands."
    if len(command) > 2000:
        return False, "Command too long for demo (max 2000 characters)."
    return True, ""


@router.post("/demo/command")
async def demo_command(req: DemoRequest, request: Request):
    """Public demo endpoint. Rate-limited. Safe subset of commands."""
    ip = _client_ip(request)

    if not _check_rate_limit(ip):
        return JSONResponse(status_code=429, content={
            "error": "Demo rate limit reached. Please try again in an hour.",
            "demo": True,
        })

    safe, reason = _is_safe(req.command)
    if not safe:
        return JSONResponse(status_code=400, content={
            "error": reason,
            "demo": True,
        })

    # Route through the Dominion stack as demo user (no private memory)
    try:
        from api.server import dominion
        stack_result = dominion.process(req.command, "demo_visitor")

        llm_response = None
        if req.use_llm:
            try:
                from models.ollama_runtime import generate
                llm_response = generate(
                    f"CRSMCPAI Alpha demo command from public visitor:\n{req.command}\n\n"
                    f"Stack context: {stack_result.get('siren',{})}\n"
                    f"Respond helpfully as Jesse AI. This is a public demo.",
                    history="",
                )
            except Exception:
                llm_response = None

        return {
            "demo": True,
            "command": req.command[:200],
            "jesse_ai_response": llm_response,
            "stack": {
                "siren": stack_result.get("siren", {}),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            "note": "Public demo. For full access, contact Jesse Martinez Junior.",
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "error": "Demo temporarily unavailable. Please try again.",
            "demo": True,
        })


@router.get("/demo/status")
async def demo_status():
    """Check if the demo endpoint is available."""
    return {
        "demo": True,
        "status": "AVAILABLE",
        "rate_limit": f"{DEMO_RATE_LIMIT} requests per hour",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
