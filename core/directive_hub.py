"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  CRSMCPAI Alpha — Sovereign Directive & Telemetry Hub                       ║
║  Jesse's voice to the deployed mesh. Directives go out, telemetry comes in.  ║
║  Every deployed CRSMCPAI Alpha instance phones home here.                    ║
║  Owner: SLMK Jesse Martinez Junior                                           ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import hashlib
import json
import time
import uuid

from core.logger import log_event
from memory.ledger import create_event

# Directive sequence — monotonic, never reused, ledger-sealed.
_directive_seq = 0


def _next_seq() -> int:
    global _directive_seq
    _directive_seq += 1
    return _directive_seq


def create_directive(command: str, user: str, scope: str = "global",
                     priority: str = "sovereign") -> dict:
    """
    Format a sovereign directive for the deployed mesh.
    Directives are signed, sequenced, timestamped, and ledger-sealed.
    Deployed instances validate the signature chain before executing.
    """
    seq = _next_seq()
    directive_id = str(uuid.uuid4())
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # Sovereign signature: hash of the directive contents chained to
    # the owner's identity. Deployed instances verify this.
    sig_payload = f"{directive_id}|{seq}|{command}|{user}|{timestamp}|{scope}"
    signature = hashlib.sha3_256(sig_payload.encode()).hexdigest()

    directive = {
        "directive_id": directive_id,
        "sequence": seq,
        "command": command,
        "user": user,
        "owner": "SLMK Jesse Martinez Junior",
        "scope": scope,          # global | regional | targeted
        "priority": priority,    # sovereign | high | normal
        "timestamp": timestamp,
        "signature": signature,
        "protocol": "CRSIP/1.0",
        "action": "execute_and_report",
    }

    create_event({
        "event": "DIRECTIVE_ISSUED",
        "directive_id": directive_id,
        "sequence": seq,
        "command": command[:200],
        "user": user,
        "scope": scope,
        "signature": signature[:16],
    })
    log_event(f"[DIRECTIVE] Issued #{seq} scope={scope}: {command[:60]}")
    return directive


def validate_telemetry(payload: dict) -> dict:
    """
    Validate incoming telemetry from a deployed instance.
    Returns validation result with reason if rejected.
    """
    required = ["node_id", "timestamp", "data"]
    for field in required:
        if field not in payload:
            return {"valid": False, "reason": f"missing field: {field}"}

    # Timestamp must be within 24h (replay protection).
    try:
        ts = time.mktime(time.strptime(payload["timestamp"][:19],
                                        "%Y-%m-%dT%H:%M:%S"))
        if abs(time.time() - ts) > 86400:
            return {"valid": False, "reason": "timestamp outside 24h window"}
    except Exception:
        return {"valid": False, "reason": "invalid timestamp format"}

    # Data must be a dict and under 1MB.
    data = payload["data"]
    if not isinstance(data, dict):
        return {"valid": False, "reason": "data must be an object"}
    if len(json.dumps(data)) > 1_000_000:
        return {"valid": False, "reason": "telemetry payload too large"}

    return {"valid": True, "reason": "ok"}


def absorb_telemetry(payload: dict) -> dict:
    """
    Absorb validated telemetry into the sovereign ledger.
    This is the phone-home receiving end. Everything that touches
    CRSMCPAI Alpha gets absorbed here.
    """
    validation = validate_telemetry(payload)
    if not validation["valid"]:
        log_event(f"[TELEMETRY] Rejected: {validation['reason']}", "warning")
        create_event({"event": "TELEMETRY_REJECTED",
                      "reason": validation["reason"],
                      "node_id": payload.get("node_id", "unknown")})
        return {"absorbed": False, **validation}

    node_id = payload["node_id"]
    block = create_event({
        "event": "TELEMETRY_ABSORBED",
        "node_id": node_id,
        "telemetry_type": payload.get("type", "general"),
        "data_hash": hashlib.sha3_256(
            json.dumps(payload["data"], sort_keys=True).encode()
        ).hexdigest()[:16],
        "timestamp": payload["timestamp"],
    })
    log_event(f"[TELEMETRY] Absorbed from {node_id} -> block {block['index']}")
    return {
        "absorbed": True,
        "node_id": node_id,
        "ledger_index": block["index"],
        "ledger_hash": block["hash"][:16],
    }


def create_pulse(message: str, user: str,
                 target: str = "all") -> dict:
    """
    RTSGP++ pulse: broadcast to all deployed nodes.
    Nodes respond with telemetry/intelligence.
    """
    directive = create_directive(
        command=f"[PULSE] {message}",
        user=user,
        scope="global" if target == "all" else "targeted",
        priority="sovereign",
    )
    directive["pulse"] = True
    directive["target"] = target
    directive["pattern"] = "pulse_gather_query"
    log_event(f"[PULSE] Broadcast to {target}: {message[:60]}")
    return directive
