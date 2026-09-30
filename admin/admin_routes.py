"""
Admin Routes — SLMK (Slide Let Me Know)
Admin: Jesse Martinez Jr.

Protected endpoints for system management, ledger inspection,
PQSVM status, and module registry.
"""
from fastapi           import APIRouter, HTTPException, Header
from security.auth     import authenticate
from memory.ledger     import get_ledger, verify_chain
from memory.vector_store import retrieve_memory, memory_count
from crsmcpai.pqsvm    import pqsvm_status
from crsmcpai.module_context_protocol import mcp
from core.config       import ADMIN_USER

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(x_user: str):
    if not authenticate(x_user):
        raise HTTPException(status_code=403, detail="Admin access denied")


@router.get("/status")
def admin_status(x_user: str = Header(default="admin")):
    """Overall system health."""
    _require_admin(x_user)
    return {
        "system":       "JESSE_AI",
        "version":      "CRSMCPAI_ALPHA",
        "admin":        ADMIN_USER,
        "pqsvm":        pqsvm_status(),
        "modules":      mcp.list_modules(),
        "memory_count": memory_count(),
        "ledger_valid": verify_chain(),
    }


@router.get("/ledger")
def admin_ledger(x_user: str = Header(default="admin")):
    """Dump the full immutable ledger."""
    _require_admin(x_user)
    chain = get_ledger()
    return {
        "ledger_length": len(chain),
        "chain_valid":   verify_chain(),
        "entries":       chain,
    }


@router.get("/memory")
def admin_memory(query: str = "", x_user: str = Header(default="admin")):
    """Inspect stored memory entries."""
    _require_admin(x_user)
    memories = retrieve_memory(query)
    return {"count": len(memories), "memories": memories}


@router.get("/pqsvm")
def admin_pqsvm(x_user: str = Header(default="admin")):
    """PQSVM module status."""
    _require_admin(x_user)
    return pqsvm_status()


@router.get("/modules")
def admin_modules(x_user: str = Header(default="admin")):
    """List all registered MCP modules."""
    _require_admin(x_user)
    return mcp.list_modules()
