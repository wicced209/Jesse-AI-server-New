"""
api/mesh_ws.py — RTSGP++ WebSocket Mesh Listener for Jesse AI / CRSMCPAI Alpha.

Self-contained FastAPI router providing the real-time mesh surface:

  * WebSocket endpoint /mesh/v4/stream accepting RTSGP++ JSON frames:
        {header: {protocol, version, messageId, timestamp, senderId,
                  recipientId, signatureType, cryptographicSignature},
         payload: {pingType, sequenceNumber, metrics, dominionToken, ...}}
  * Node registry (in-memory; Postgres port comes later): nodes are
    registered/updated on HEARTBEAT and tracked with nodeId, instanceType,
    sinSegment, status, lastPingTimestamp, telemetryMetrics.
  * Ping types: HEARTBEAT -> PONG_ACKNOWLEDGED,
                DEEP_DIAGNOSTIC -> DIAGNOSTIC_ACKNOWLEDGED,
                SYNC_REQUEST -> SYNC_ACKNOWLEDGED.
  * Dominion terms check: 'jesse_martinez_jr' and 'CRSMCPAI_ALPHA_CORE'
    always pass; a simple blocklist (empty by default) quarantines others.
  * SIN segments: SIN-01-COMMAND, SIN-02-CLEARINGHOUSE, SIN-03-EDGE-SWARM.
  * GET /mesh/v4/nodes  - list all registered nodes (real state).
  * GET /mesh/v4/status - hub liveness + counts (real state).

Mount in the main app with:
    from api.mesh_ws import router as mesh_ws_router
    app.include_router(mesh_ws_router)
"""

import json
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

router = APIRouter()

PROTOCOL = "RTSGP++"
PROTOCOL_VERSION = "2.4.0-quantum"
HUB_SENDER_ID = "CRSMCPAI_ALPHA_CORE"

# ---------------------------------------------------------------------------
# SIN network segments
# ---------------------------------------------------------------------------

SIN_01_COMMAND = "SIN-01-COMMAND"
SIN_02_CLEARINGHOUSE = "SIN-02-CLEARINGHOUSE"
SIN_03_EDGE_SWARM = "SIN-03-EDGE-SWARM"
VALID_SIN_SEGMENTS = {SIN_01_COMMAND, SIN_02_CLEARINGHOUSE, SIN_03_EDGE_SWARM}

# Default segment assignment by instance type.
_INSTANCE_TO_SIN = {
    "CRS_ALPHA_CORE": SIN_01_COMMAND,
    "DOMINION_RELAY": SIN_02_CLEARINGHOUSE,
    "EDGE_AGENT": SIN_03_EDGE_SWARM,
    "QUANTUM_VAULT": SIN_02_CLEARINGHOUSE,
}

# ---------------------------------------------------------------------------
# Dominion terms enforcement (simple, in-memory)
# ---------------------------------------------------------------------------

_ALWAYS_ALLOWED = {"jesse_martinez_jr", HUB_SENDER_ID}
_blocklist: set = set()  # quarantined node ids; empty by default


def dominion_terms_check(sender_id: str, ping_type: str) -> bool:
    """True if the sender may proceed. Superadmin and core always pass."""
    if sender_id in _ALWAYS_ALLOWED:
        return True
    if sender_id in _blocklist:
        return False
    return True


def quarantine_node(sender_id: str) -> None:
    _blocklist.add(sender_id)


# ---------------------------------------------------------------------------
# Node registry (in-memory)
# ---------------------------------------------------------------------------

_nodes: Dict[str, Dict[str, Any]] = {}


def _resolve_sin_segment(instance_type: str, requested: Optional[str]) -> str:
    if requested in VALID_SIN_SEGMENTS:
        return requested
    return _INSTANCE_TO_SIN.get(instance_type, SIN_03_EDGE_SWARM)


def register_or_update_node(sender_id: str, payload: Dict[str, Any],
                            header: Dict[str, Any]) -> Dict[str, Any]:
    now_ms = int(time.time() * 1000)
    instance_type = str(payload.get("instanceType", "EDGE_AGENT"))
    sin_segment = _resolve_sin_segment(
        instance_type, payload.get("sinSegment") or header.get("sinSegment"))
    metrics = payload.get("metrics", {}) or {}

    record = _nodes.get(sender_id)
    if record is None:
        record = {
            "nodeId": sender_id,
            "instanceType": instance_type,
            "sinSegment": sin_segment,
            "status": "ACTIVE",
            "firstSeenTimestamp": now_ms,
            "telemetryMetrics": {},
        }
        _nodes[sender_id] = record

    record["instanceType"] = instance_type
    record["sinSegment"] = sin_segment
    record["status"] = "ACTIVE"
    record["lastPingTimestamp"] = now_ms
    record["telemetryMetrics"] = {
        "cpuUtilization": metrics.get("cpuUtilization"),
        "memoryAllocatedBytes": metrics.get("memoryAllocatedBytes"),
        "activeLedgerHeight": metrics.get("activeLedgerHeight"),
        "latencyMs": metrics.get("latencyMs"),
        "computeLoadPct": metrics.get("computeLoadPct"),
        "activeConnections": metrics.get("activeConnections"),
    }
    return record


def list_nodes() -> List[Dict[str, Any]]:
    return list(_nodes.values())


def active_node_count() -> int:
    return sum(1 for n in _nodes.values() if n.get("status") == "ACTIVE")


# ---------------------------------------------------------------------------
# Frame handling
# ---------------------------------------------------------------------------

def _ack_frame(recipient_id: str, status: str,
               acknowledged_seq: Any) -> Dict[str, Any]:
    return {
        "header": {
            "protocol": PROTOCOL,
            "version": PROTOCOL_VERSION,
            "messageId": f"ACK-{uuid.uuid4().hex[:12]}",
            "timestamp": int(time.time() * 1000),
            "senderId": HUB_SENDER_ID,
            "recipientId": recipient_id,
            "signatureType": "HUB-SIGNED",
            "cryptographicSignature": "",
        },
        "payload": {
            "status": status,
            "acknowledgedSeq": acknowledged_seq,
        },
    }


def handle_frame(frame: Dict[str, Any]) -> Dict[str, Any]:
    """Process one inbound RTSGP++ frame; return the response frame."""
    header = frame.get("header", {}) or {}
    payload = frame.get("payload", {}) or {}

    sender_id = str(header.get("senderId", "UNKNOWN"))
    protocol = header.get("protocol")
    ping_type = str(payload.get("pingType", "HEARTBEAT")).upper()
    seq = payload.get("sequenceNumber", 0)

    if protocol != PROTOCOL:
        return {
            "header": header,
            "payload": {"status": "PROTOCOL_MISMATCH",
                        "expected": PROTOCOL},
        }

    if not dominion_terms_check(sender_id, ping_type):
        return {
            "header": header,
            "payload": {"status": "DOMINION_TERMS_VIOLATION_QUARANTINED"},
        }

    # Register / refresh the node on any valid ping.
    register_or_update_node(sender_id, payload, header)

    if ping_type == "HEARTBEAT":
        return _ack_frame(sender_id, "PONG_ACKNOWLEDGED", seq)
    if ping_type == "DEEP_DIAGNOSTIC":
        return _ack_frame(sender_id, "DIAGNOSTIC_ACKNOWLEDGED", seq)
    if ping_type == "SYNC_REQUEST":
        return _ack_frame(sender_id, "SYNC_ACKNOWLEDGED", seq)

    return _ack_frame(sender_id, "UNKNOWN_PING_TYPE_ACKNOWLEDGED", seq)


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@router.websocket("/mesh/v4/stream")
async def mesh_stream(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                frame = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "header": {},
                    "payload": {"status": "MALFORMED_FRAME"},
                }))
                continue
            response = handle_frame(frame)
            await websocket.send_text(json.dumps(response))
    except WebSocketDisconnect:
        pass


# ---------------------------------------------------------------------------
# HTTP introspection (real state)
# ---------------------------------------------------------------------------

@router.get("/mesh/v4/nodes")
def mesh_nodes():
    return JSONResponse({"nodes": list_nodes(), "count": len(_nodes)})


@router.get("/mesh/v4/status")
def mesh_status():
    return JSONResponse({
        "online": True,
        "protocol": PROTOCOL,
        "version": PROTOCOL_VERSION,
        "node_count": len(_nodes),
        "active_nodes": active_node_count(),
        "sin_segments": sorted(VALID_SIN_SEGMENTS),
    })
