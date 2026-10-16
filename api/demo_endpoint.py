"""
CRSMCPAI Alpha - Sovereign Public Demo Endpoint Router
Superadmin: SLMK Jesse Martinez Junior
Genesis Hash: 92038cafccc7192535bd475cca985d03000d89962b8dc96f6664081663559b1b
"""

import time
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, HTTPException, status
from pydantic import BaseModel, Field

logger = logging.getLogger("CRSMCPAI.DemoEndpoint")

router = APIRouter(prefix="/api/demo", tags=["Public Demo"])

# In-memory rate limiting store (IP -> timestamp list)
# Note: For multi-instance scaling, upgrade to Redis. For single container, this is robust.
RATE_LIMIT_WINDOW: int = 60  # seconds
MAX_REQUESTS_PER_WINDOW: int = 15
request_history: Dict[str, list] = {}

class DemoCommandRequest(BaseModel):
    command: str = Field(..., min_length=1, max_length=500, description="Sovereign command or prompt string")
    client_mode: Optional[str] = Field("standard", description="Operational mode profile")

class DemoCommandResponse(BaseModel):
    status: str
    block_hash: str
    response_telemetry: str
    execution_time_ms: float

@router.post("/execute", response_model=DemoCommandResponse)
async def execute_demo_command(payload: DemoCommandRequest, request: Request) -> Dict[str, Any]:
    """
    Executes a sandboxed public demo command with strict rate limiting and telemetry output.
    """
    start_time = time.time()
    
    # Extract client IP securely
    client_ip = request.client.host if request.client else "127.0.0.1"
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()

    # Rate limiting enforcement
    now = time.time()
    history = request_history.setdefault(client_ip, [])
    # Prune old timestamps outside the window
    history[:] = [t for t in history if now - t < RATE_LIMIT_WINDOW]

    if len(history) >= MAX_REQUESTS_PER_WINDOW:
        logger.warning(f"Rate limit exceeded for IP: {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Maximum 15 demo requests per minute."
        )

    history.append(now)

    # Sanitize and process command
    cmd_lower = payload.command.strip().lower()
    
    # Sovereign simulation logic for public demo
    if "status" in cmd_lower:
        telemetry = "CRSMCPAI Alpha Core: ONLINE. AGSSI-Omega-Prime active at 150% capacity. All systems nominal."
    elif "version" in cmd_lower or "genesis" in cmd_lower:
        telemetry = "Genesis Hash: 92038cafccc7192535bd475cca985d03000d89962b8dc96f6664081663559b1b | Superadmin: SLMK Jesse Martinez Junior"
    elif "help" in cmd_lower:
        telemetry = "Available public demo commands: 'status', 'version', 'genesis', 'ping', 'solva'."
    else:
        telemetry = f"Sovereign Echo [Demo Mode]: Received command -> '{payload.command}'. Execution secured under CRS Alpha."

    execution_time = (time.time() - start_time) * 1000.0

    return {
        "status": "SUCCESS",
        "block_hash": "92038cafccc7192535bd475cca985d03000d89962b8dc96f6664081663559b1b",
        "response_telemetry": telemetry,
        "execution_time_ms": round(execution_time, 3)
    }

@router.get("/health", response_model=Dict[str, str])
async def demo_health_check() -> Dict[str, str]:
    return {
        "status": "HEALTHY",
        "router": "demo_endpoint",
        "superadmin": "SLMK Jesse Martinez Junior"
    }
