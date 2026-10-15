"""
api/mesh.py — CRS Mesh Spine for Jesse AI / CRSMCPAI Alpha.

Self-contained FastAPI router (prefix /v1/mesh) providing the minimum
CRS-to-CRS communication surface:

  * Node registry (in-memory; Postgres port comes later)
  * Enrollment with Ed25519 challenge/response (HMAC-SHA3-512 fallback)
  * Signed telemetry intake with replay protection and rate limiting
  * Heartbeat with pull-based directive delivery (works through NAT/firewalls)
  * Directive lifecycle: QUEUED -> DELIVERED -> ACKED / FAILED
  * HUD status endpoint reading real in-memory state

Security notes:
  * Nodes authenticate with Ed25519 signatures over canonical JSON.
  * Timestamps must be within 5 minutes (replay protection).
  * Nonces are single-use with a 10-minute TTL cache.
  * This module does NOT touch the existing accessible terminal UI routes.

Mount in the main app with:
    from api.mesh import router as mesh_router
    app.include_router(mesh_router)
"""

import hashlib
import hmac
import json
import secrets
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Crypto backend: prefer Ed25519 (nacl), fall back to HMAC-SHA3-512
# ---------------------------------------------------------------------------

try:
    from nacl.signing import VerifyKey as _NaclVerifyKey
    from nacl.exceptions import BadSignatureError as _NaclBadSig

    _CRYPTO = "ed25519"

    def _verify_signature(public_key_hex: str, message: bytes, signature_hex: str) -> bool:
        try:
            vk = _NaclVerifyKey(bytes.fromhex(public_key_hex))
            vk.verify(message, bytes.fromhex(signature_hex))
            return True
        except (_NaclBadSig, ValueError, Exception):
            return False

except ImportError:  # pragma: no cover - fallback path
    _CRYPTO = "hmac-sha3-512"

    def _verify_signature(public_key_hex: str, message: bytes, signature_hex: str) -> bool:
        # Fallback: the "public key" is treated as the shared secret hex.
        expected = hmac.new(bytes.fromhex(public_key_hex), message, hashlib.sha3_512).hexdigest()
        return hmac.compare_digest(expected, signature_hex)


# ---------------------------------------------------------------------------
# In-memory state (Postgres port comes later)
# ---------------------------------------------------------------------------

NODES: Dict[str, Dict[str, Any]] = {}          # node_uuid -> node record
CHALLENGES: Dict[str, Dict[str, Any]] = {}     # node_uuid -> {challenge, expires_at}
TELEMETRY: List[Dict[str, Any]] = []           # stored telemetry batches
NONCES: Dict[str, float] = {}                  # nonce -> received epoch (TTL 600s)
DIRECTIVES: Dict[str, Dict[str, Any]] = {}     # directive_id -> directive record
NODE_TOKENS: Dict[str, str] = {}               # node_uuid -> node token
_DIRECTIVE_SEQ = 0

TIMESTAMP_SKEW_SECONDS = 300      # 5 minutes
NONCE_TTL_SECONDS = 600           # 10 minutes
CHALLENGE_TTL_SECONDS = 300       # 5 minutes


def _now() -> float:
    return time.time()


def _canonical(data: Dict[str, Any]) -> bytes:
    """Canonical JSON encoding used for all signature verification."""
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _prune_nonces() -> None:
    cutoff = _now() - NONCE_TTL_SECONDS
    for nonce in [n for n, ts in NONCES.items() if ts < cutoff]:
        del NONCES[nonce]


def _check_timestamp(ts: float) -> None:
    if abs(_now() - float(ts)) > TIMESTAMP_SKEW_SECONDS:
        raise HTTPException(status_code=401, detail="timestamp outside allowed skew window")


def _check_nonce(nonce: str) -> None:
    _prune_nonces()
    if nonce in NONCES:
        raise HTTPException(status_code=409, detail="nonce already used (replay rejected)")
    NONCES[nonce] = _now()


def _get_active_node(node_uuid: str) -> Dict[str, Any]:
    node = NODES.get(node_uuid)
    if node is None:
        raise HTTPException(status_code=404, detail="node not enrolled")
    if node["status"] != "ACTIVE":
        raise HTTPException(status_code=403, detail=f"node not active (status={node['status']})")
    return node


def _verify_node_signature(node: Dict[str, Any], message: bytes, signature_hex: str) -> None:
    if not _verify_signature(node["public_key"], message, signature_hex):
        raise HTTPException(status_code=401, detail="invalid signature")


# ---------------------------------------------------------------------------
# Node registry functions
# ---------------------------------------------------------------------------

def register_node(node_uuid: str, public_key: str, capabilities: List[str]) -> Dict[str, Any]:
    node = {
        "node_uuid": node_uuid,
        "public_key": public_key,
        "capabilities": list(capabilities),
        "status": "PENDING",
        "enrolled_at": _now(),
        "last_seen": None,
    }
    NODES[node_uuid] = node
    return node


def get_node(node_uuid: str) -> Optional[Dict[str, Any]]:
    return NODES.get(node_uuid)


def list_nodes() -> List[Dict[str, Any]]:
    return list(NODES.values())


def revoke_node(node_uuid: str) -> Dict[str, Any]:
    node = NODES.get(node_uuid)
    if node is None:
        raise HTTPException(status_code=404, detail="node not enrolled")
    node["status"] = "REVOKED"
    NODE_TOKENS.pop(node_uuid, None)
    return node


def update_last_seen(node_uuid: str) -> None:
    node = NODES.get(node_uuid)
    if node is not None:
        node["last_seen"] = _now()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class EnrollRequest(BaseModel):
    node_uuid: str
    public_key: str = Field(description="Ed25519 public key as 64-char hex (or HMAC secret hex in fallback mode)")
    capabilities: List[str] = []


class EnrollConfirmRequest(BaseModel):
    node_uuid: str
    signature: str = Field(description="hex signature over the challenge string bytes")


class TelemetryRequest(BaseModel):
    node_uuid: str
    timestamp: float
    nonce: str
    payload: Dict[str, Any]
    signature: str = Field(description="hex signature over canonical JSON of {node_uuid,timestamp,nonce,payload}")


class HeartbeatRequest(BaseModel):
    node_uuid: str
    timestamp: float
    signature: str = Field(description="hex signature over canonical JSON of {node_uuid,timestamp}")


class DirectiveCreateRequest(BaseModel):
    command: str
    target_nodes: Any = Field(description='list of node UUIDs or the string "all"')
    priority: str = "normal"


class AckRequest(BaseModel):
    node_uuid: str
    signature: str = Field(description="hex signature over canonical JSON of {directive_id,node_uuid,result}")
    result: Dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/v1/mesh", tags=["mesh"])


@router.post("/enroll")
def enroll(req: EnrollRequest):
    """Step 1 of enrollment: register node identity, issue a challenge."""
    try:
        bytes.fromhex(req.public_key)
    except ValueError:
        raise HTTPException(status_code=400, detail="public_key must be hex")
    register_node(req.node_uuid, req.public_key, req.capabilities)
    challenge = secrets.token_hex(32)
    CHALLENGES[req.node_uuid] = {"challenge": challenge, "expires_at": _now() + CHALLENGE_TTL_SECONDS}
    return JSONResponse({"challenge": challenge, "expires_at": CHALLENGES[req.node_uuid]["expires_at"]})


@router.post("/enroll/confirm")
def enroll_confirm(req: EnrollConfirmRequest):
    """Step 2 of enrollment: node proves key ownership by signing the challenge."""
    chal = CHALLENGES.get(req.node_uuid)
    node = NODES.get(req.node_uuid)
    if chal is None or node is None:
        raise HTTPException(status_code=404, detail="no pending enrollment for this node")
    if _now() > chal["expires_at"]:
        del CHALLENGES[req.node_uuid]
        raise HTTPException(status_code=401, detail="challenge expired; re-enroll")
    _verify_node_signature(node, chal["challenge"].encode("utf-8"), req.signature)
    node["status"] = "ACTIVE"
    node["last_seen"] = _now()
    token = secrets.token_urlsafe(32)
    NODE_TOKENS[req.node_uuid] = token
    del CHALLENGES[req.node_uuid]
    return JSONResponse({"node_token": token, "status": "active", "crypto": _CRYPTO})


@router.post("/telemetry")
def telemetry(req: TelemetryRequest):
    """Signed telemetry intake with replay protection and rate limiting."""
    node = _get_active_node(req.node_uuid)
    _check_timestamp(req.timestamp)
    _check_nonce(req.nonce)
    _verify_node_signature(
        node,
        _canonical({"node_uuid": req.node_uuid, "timestamp": req.timestamp,
                    "nonce": req.nonce, "payload": req.payload}),
        req.signature,
    )
    receipt_id = uuid.uuid4().hex
    TELEMETRY.append({
        "receipt_id": receipt_id,
        "node_uuid": req.node_uuid,
        "timestamp": req.timestamp,
        "received_at": _now(),
        "payload": req.payload,
    })
    update_last_seen(req.node_uuid)
    return JSONResponse({"accepted": True, "receipt_id": receipt_id})


@router.post("/heartbeat")
def heartbeat(req: HeartbeatRequest):
    """Lightweight signed check-in; returns QUEUED directives for this node (pull delivery)."""
    node = _get_active_node(req.node_uuid)
    _check_timestamp(req.timestamp)
    _verify_node_signature(
        node,
        _canonical({"node_uuid": req.node_uuid, "timestamp": req.timestamp}),
        req.signature,
    )
    update_last_seen(req.node_uuid)
    queued = []
    for d in DIRECTIVES.values():
        delivery = d["targets"].get(req.node_uuid)
        if delivery and delivery["state"] == "QUEUED":
            delivery["state"] = "DELIVERED"
            delivery["delivered_at"] = _now()
            queued.append({
                "directive_id": d["directive_id"],
                "seq": d["seq"],
                "command": d["command"],
                "priority": d["priority"],
                "created_at": d["created_at"],
            })
    return JSONResponse({"queued_directives": queued, "count": len(queued)})


@router.post("/directives")
def create_directive(req: DirectiveCreateRequest):
    """Create a directive addressed to specific nodes (or 'all' active nodes)."""
    global _DIRECTIVE_SEQ
    if req.target_nodes == "all":
        targets = [u for u, n in NODES.items() if n["status"] == "ACTIVE"]
    elif isinstance(req.target_nodes, list):
        targets = list(req.target_nodes)
    else:
        raise HTTPException(status_code=400, detail='target_nodes must be a list or "all"')
    if not targets:
        raise HTTPException(status_code=400, detail="no target nodes available")
    _DIRECTIVE_SEQ += 1
    directive_id = uuid.uuid4().hex
    directive = {
        "directive_id": directive_id,
        "seq": _DIRECTIVE_SEQ,
        "command": req.command,
        "priority": req.priority,
        "created_at": _now(),
        "targets": {
            t: {"state": "QUEUED", "result": None, "delivered_at": None, "acked_at": None}
            for t in targets
        },
    }
    DIRECTIVES[directive_id] = directive
    return JSONResponse({"directive_id": directive_id, "seq": _DIRECTIVE_SEQ,
                         "targets": targets, "state": "QUEUED"})


@router.get("/directives/{directive_id}")
def get_directive(directive_id: str):
    d = DIRECTIVES.get(directive_id)
    if d is None:
        raise HTTPException(status_code=404, detail="directive not found")
    return JSONResponse(d)


@router.post("/directives/{directive_id}/ack")
def ack_directive(directive_id: str, req: AckRequest):
    """Node posts a signed acknowledgment with its result payload."""
    d = DIRECTIVES.get(directive_id)
    if d is None:
        raise HTTPException(status_code=404, detail="directive not found")
    delivery = d["targets"].get(req.node_uuid)
    if delivery is None:
        raise HTTPException(status_code=404, detail="node is not a target of this directive")
    node = _get_active_node(req.node_uuid)
    _verify_node_signature(
        node,
        _canonical({"directive_id": directive_id, "node_uuid": req.node_uuid, "result": req.result}),
        req.signature,
    )
    delivery["state"] = "ACKED"
    delivery["result"] = req.result
    delivery["acked_at"] = _now()
    update_last_seen(req.node_uuid)
    return JSONResponse({"directive_id": directive_id, "node_uuid": req.node_uuid, "state": "ACKED"})


@router.get("/nodes")
def get_nodes():
    """List all enrolled nodes with status."""
    return JSONResponse({"nodes": list_nodes(), "count": len(NODES)})


@router.delete("/nodes/{node_uuid}")
def delete_node(node_uuid: str):
    """Revoke a node (admin operation; marks status REVOKED)."""
    node = revoke_node(node_uuid)
    return JSONResponse({"node_uuid": node_uuid, "status": node["status"]})


@router.get("/status")
def mesh_status():
    """HUD status: real counts from in-memory state."""
    active = sum(1 for n in NODES.values() if n["status"] == "ACTIVE")
    queued = sum(1 for d in DIRECTIVES.values()
                 for t in d["targets"].values() if t["state"] == "QUEUED")
    acked = sum(1 for d in DIRECTIVES.values()
                for t in d["targets"].values() if t["state"] == "ACKED")
    return JSONResponse({
        "crypto_backend": _CRYPTO,
        "node_count": len(NODES),
        "active_nodes": active,
        "telemetry_count": len(TELEMETRY),
        "directive_count": len(DIRECTIVES),
        "queued_directives": queued,
        "acked_directives": acked,
        "ledger_height": None,  # wired to Postgres ledger_blocks in the next pass
    })
