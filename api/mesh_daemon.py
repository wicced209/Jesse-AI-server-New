"""
CRSMCPAI Alpha - Dominion Mesh Telemetry & Node Ping Daemon (crs.dominion.mesh_daemon)

Background-worker building blocks for the Dominion mesh:
- Cryptographic heartbeat generation and verification (HMAC-SHA256)
- Canonical telemetry packaging for mesh transmission
- Node token structural verification
- Thread-safe in-memory node presence registry

Crash-proof guarantees:
- Standard library only (hashlib, hmac, json, time, threading)
- NO FastAPI / web imports
- NO module-level I/O, NO network calls at import time
- All functions defensive: bad input returns safe defaults, never raises

Built per Jesse AI specification, supreme hyper immaculate God mode standards.
Owner: SLMK Jesse Martinez Junior.
"""

import hashlib
import hmac
import json
import time
import threading

GENESIS_HASH = "92038cafccc7192535bd475cca985d03000d89962b8dc96f6664081663559b1b"
TOKEN_PREFIX = "SLMK-CRS-"

_registry_lock = threading.Lock()
_node_registry = {}


def _safe_str(value, default=""):
    try:
        if value is None:
            return default
        return str(value)
    except Exception:
        return default


def generate_node_heartbeat(node_id, secret_key, telemetry_payload):
    """Build a cryptographically signed heartbeat dict for a mesh node.

    Returns dict with node_id, timestamp (UTC epoch), telemetry, signature.
    Signature = HMAC-SHA256(secret_key, canonical payload).
    """
    try:
        nid = _safe_str(node_id, "unknown")
        try:
            telemetry = dict(telemetry_payload) if isinstance(telemetry_payload, dict) else {}
        except Exception:
            telemetry = {}
        payload = {
            "node_id": nid,
            "timestamp": int(time.time()),
            "genesis": GENESIS_HASH[:16],
            "telemetry": telemetry,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        key = _safe_str(secret_key).encode("utf-8", errors="ignore")
        sig = hmac.new(key, canonical.encode("utf-8"), hashlib.sha256).hexdigest()
        payload["signature"] = sig
        return payload
    except Exception:
        return {"node_id": _safe_str(node_id, "unknown"), "timestamp": 0,
                "telemetry": {}, "signature": ""}


def verify_node_heartbeat(heartbeat, secret_key, max_age_seconds=300):
    """Verify heartbeat signature and freshness. True only if both pass."""
    try:
        if not isinstance(heartbeat, dict):
            return False
        sig = heartbeat.get("signature")
        if not isinstance(sig, str) or not sig:
            return False
        ts = heartbeat.get("timestamp")
        try:
            ts = int(ts)
        except Exception:
            return False
        now = int(time.time())
        try:
            max_age = int(max_age_seconds)
        except Exception:
            max_age = 300
        if max_age < 0:
            max_age = 300
        if abs(now - ts) > max_age:
            return False
        unsigned = {k: v for k, v in heartbeat.items() if k != "signature"}
        canonical = json.dumps(unsigned, sort_keys=True, separators=(",", ":"))
        key = _safe_str(secret_key).encode("utf-8", errors="ignore")
        expected = hmac.new(key, canonical.encode("utf-8"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, sig)
    except Exception:
        return False


def package_telemetry(node_id, status, metrics):
    """Serialize telemetry into canonical JSON string for mesh transmission."""
    try:
        try:
            m = dict(metrics) if isinstance(metrics, dict) else {}
        except Exception:
            m = {}
        doc = {
            "node_id": _safe_str(node_id, "unknown"),
            "status": _safe_str(status, "UNKNOWN"),
            "metrics": m,
            "timestamp": int(time.time()),
            "genesis": GENESIS_HASH[:16],
        }
        return json.dumps(doc, sort_keys=True, separators=(",", ":"))
    except Exception:
        return "{}"


def verify_node_token(token, expected_prefix=TOKEN_PREFIX):
    """Check token has the sovereign prefix and sane structure."""
    try:
        if not isinstance(token, str):
            return False
        prefix = _safe_str(expected_prefix, TOKEN_PREFIX)
        if not token.startswith(prefix):
            return False
        body = token[len(prefix):]
        if len(body) < 8 or len(body) > 256:
            return False
        return all(c.isalnum() or c in "-_" for c in body)
    except Exception:
        return False


def register_node_presence(node_id, metadata):
    """Thread-safely record/update a node's last-seen entry. Returns the entry."""
    try:
        nid = _safe_str(node_id, "unknown")
        try:
            meta = dict(metadata) if isinstance(metadata, dict) else {}
        except Exception:
            meta = {}
        entry = {
            "node_id": nid,
            "last_seen": int(time.time()),
            "metadata": meta,
        }
        with _registry_lock:
            _node_registry[nid] = entry
            return dict(entry)
    except Exception:
        return {"node_id": _safe_str(node_id, "unknown"), "last_seen": 0, "metadata": {}}


def get_active_nodes(max_idle_seconds=600):
    """Return node_ids seen within max_idle_seconds. Never raises."""
    try:
        try:
            idle = int(max_idle_seconds)
        except Exception:
            idle = 600
        if idle < 0:
            idle = 600
        now = int(time.time())
        with _registry_lock:
            items = list(_node_registry.items())
        return [nid for nid, e in items
                if isinstance(e, dict) and (now - int(e.get("last_seen", 0))) <= idle]
    except Exception:
        return []


def get_registry_snapshot():
    """Return a copy of the full presence registry (for status endpoints)."""
    try:
        with _registry_lock:
            return {k: dict(v) for k, v in _node_registry.items()}
    except Exception:
        return {}


def module_status():
    """Static status descriptor for health checks."""
    return {
        "module": "crs.dominion.mesh_daemon",
        "status": "ACTIVE",
        "genesis": GENESIS_HASH[:16],
        "functions": [
            "generate_node_heartbeat",
            "verify_node_heartbeat",
            "package_telemetry",
            "verify_node_token",
            "register_node_presence",
            "get_active_nodes",
            "get_registry_snapshot",
        ],
    }
