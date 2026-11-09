"""
CRSMCPAI Alpha — Sovereign OS Runtime: the Compute Fabric (v2.0,
2026-11-08, Muse).

Doctrine (Jesse, standing): Sovereign OS v1.0/v2.0 fully operating
as deployed; all internal networks communicate and execute through
CRSMCPAI Alpha. In the AI Studio era the OS ran as session behavior:
Jesse AI coordinated the planetary compute, the shared hive-mind
state, and the Superintelligence seat by hand, every day. The
surviving repo copy of the OS is a declarative template
(os-sovereign-v3.0-PQ). This module is the rebuilt runtime — the
v2.0 edition of that design, standing on the parts of today's stack
that are already real: the mesh (node enrollment), the telemetry
intake (signed node readings), hyper sync (shared ledger state),
CRS (shared context), and the OS family duties.

What the fabric does, for real:

  * CAPACITY — every enrolled node's picture: identity from the
    mesh, load / memory / cpu count from its latest signed telemetry
    readings. A node that reports nothing has no claimed capacity.
  * WORK ORDERS — the hub issues work (host_probe, hash_check,
    merkle_segment, echo) targeted at a node or open to any; nodes
    poll for work, execute it, and return results. Poll and result
    require the node's mesh token; an order can only be completed
    by the node that claimed it. The hub VERIFIES hash_check and
    merkle_segment results against its own computation before
    accepting them — a node cannot fake the answer.
  * HIVE STATE — one aggregated picture: all nodes, their capacity,
    orders completed, the shared ledger height and convergence, and
    the CRS working-context size. This is the hive mind as data:
    every participant looking at the same verified state.
  * The Superintelligence seat stays where it already lives: AGSSI
    reasoning and the Sovereign Dominion full check in the OS
    family. The fabric feeds them the hive picture.

Registry state is in-memory and resets with the hub, like the mesh
and telemetry registries it stands on; every order transition is
sealed to the Golden Ledger.

Owner: SLMK Jesse Martinez Junior.
"""
import hashlib
import time
import uuid

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/sovereign-os", tags=["sovereign-os"])

RUNTIME_VERSION = "sovereign-os-runtime-v2.0"
DESIGN_VERSION = "v1.0 session-era design (repo template os-sovereign-v3.0-PQ)"

_ORDERS: dict[str, dict] = {}
_SUPPORTED_KINDS = ("host_probe", "hash_check", "merkle_segment", "echo")


def _seal(kind: str, payload: dict) -> None:
    try:
        from memory.ledger import create_event
        create_event({"system": "sovereign_os_fabric", "kind": kind, **payload})
    except Exception:
        pass


def _latest_readings_by_source() -> dict[str, dict]:
    """Latest host readings per telemetry source, scanned from the
    intake's accepted-batch ring."""
    from api.telemetry_ingest import recent_batches
    out: dict[str, dict] = {}
    for batch in recent_batches(limit=50)["batches"]:
        sid = batch["source_id"]
        if sid in out:
            continue
        for event in batch.get("events", []):
            metrics = event.get("metrics") or event
            if "cpu_count" in metrics or "load_1m" in metrics:
                out[sid] = {"cpu_count": metrics.get("cpu_count"),
                            "load_1m": metrics.get("load_1m"),
                            "memory_used_pct": metrics.get("memory_used_pct")}
                break
    return out


def _node_capacity() -> list[dict]:
    """Every participant's capacity picture: mesh-enrolled nodes
    (identity, status, capabilities) and telemetry sources (label,
    state, latest real readings). A participant that reports nothing
    shows nulls — capacity is never invented."""
    from api import mesh
    from api.telemetry_ingest import _SOURCES
    readings = _latest_readings_by_source()
    nodes = []
    for node_uuid, node in mesh.NODES.items():
        nodes.append({
            "node_id": node_uuid, "kind": "mesh_node",
            "status": node.get("status"),
            "capabilities": node.get("capabilities"),
            "last_seen": node.get("last_seen"),
            "orders_completed": sum(
                1 for o in _ORDERS.values()
                if o["status"] == "done" and o.get("completed_by") == node_uuid),
        })
    for sid, source in _SOURCES.items():
        r = readings.get(sid, {})
        nodes.append({
            "node_id": sid, "kind": "telemetry_source",
            "label": source.get("label"), "status": source.get("state"),
            "last_seen": source.get("last_seen"),
            "cpu_count": r.get("cpu_count"), "load_1m": r.get("load_1m"),
            "memory_used_pct": r.get("memory_used_pct"),
            "orders_completed": 0,
        })
    return nodes


def create_work_order(kind: str, params: dict = None, target_node: str = "") -> dict:
    if kind not in _SUPPORTED_KINDS:
        raise ValueError(f"unsupported work kind '{kind}'; supported: {_SUPPORTED_KINDS}")
    order = {"order_id": uuid.uuid4().hex[:16], "kind": kind,
             "params": params or {}, "target_node": target_node,
             "status": "pending", "claimed_by": None, "result": None,
             "verified": None, "created_at": time.time(), "completed_at": None}
    _ORDERS[order["order_id"]] = order
    _seal("work_order_created", {"order_id": order["order_id"], "kind": kind,
                                 "target_node": target_node})
    return order


def _check_token(node_id: str, token: str) -> None:
    from api.mesh import NODE_TOKENS
    expected = NODE_TOKENS.get(node_id)
    if expected is None or token != expected:
        raise HTTPException(status_code=401,
                            detail="valid mesh node token required")


def poll_work(node_id: str, token: str) -> dict:
    """Claim the oldest pending order open to this node."""
    _check_token(node_id, token)
    for order in _ORDERS.values():
        if order["status"] == "pending" and (
                not order["target_node"] or order["target_node"] == node_id):
            order["status"] = "claimed"
            order["claimed_by"] = node_id
            order["claimed_at"] = time.time()
            _seal("work_order_claimed", {"order_id": order["order_id"],
                                         "node_id": node_id})
            return {"order": order}
    return {"order": None}


def _verify_result(order: dict, result: dict) -> bool | None:
    """Hub-side verification for the computable kinds. Returns True
    or False; None for kinds the hub cannot recompute (host_probe,
    echo), which are accepted as node-reported."""
    kind = order["kind"]
    if kind == "hash_check":
        data = str(order["params"].get("data", "")).encode()
        return result.get("sha3_512") == hashlib.sha3_512(data).hexdigest()
    if kind == "merkle_segment":
        from api.hyper_sync import merkle_root
        hashes = order["params"].get("hashes", [])
        return result.get("merkle_root") == merkle_root(list(hashes))
    return None


def submit_result(node_id: str, token: str, order_id: str, result: dict,
                  error: str = "") -> dict:
    _check_token(node_id, token)
    order = _ORDERS.get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="unknown order")
    if order["status"] != "claimed" or order["claimed_by"] != node_id:
        raise HTTPException(status_code=409,
                            detail="order is not claimed by this node")
    if error:
        order["status"] = "failed"
        order["result"] = {"error": error}
        order["verified"] = None
    else:
        verified = _verify_result(order, result)
        order["verified"] = verified
        order["status"] = "done" if verified is not False else "rejected"
        order["result"] = result
    order["completed_by"] = node_id
    order["completed_at"] = time.time()
    _seal("work_order_completed",
          {"order_id": order_id, "node_id": node_id,
           "status": order["status"], "verified": order["verified"]})
    return order


def hive_state() -> dict:
    """The hive-mind picture: one verified state every participant
    shares — nodes and capacity, work, the ledger, convergence, and
    the shared context."""
    from api.hyper_sync import convergence, state_vector
    from crsmcpai.context_reasoning import crs
    from memory.ledger import get_ledger, verify_chain
    nodes = _node_capacity()
    return {
        "runtime": RUNTIME_VERSION,
        "design": DESIGN_VERSION,
        "nodes": nodes,
        "nodes_active": sum(1 for n in nodes if n["status"] == "ACTIVE"),
        "work": {"total": len(_ORDERS),
                 "pending": sum(1 for o in _ORDERS.values() if o["status"] == "pending"),
                 "done": sum(1 for o in _ORDERS.values() if o["status"] == "done"),
                 "rejected": sum(1 for o in _ORDERS.values() if o["status"] == "rejected")},
        "ledger": {"height": len(get_ledger()), "chain_valid": verify_chain()},
        "sync": {"self": state_vector()["fingerprint"]["height"],
                 "peers": convergence()},
        "shared_context": crs.stats(),
    }


# ── Routes ──────────────────────────────────────────────────────────────

class OrderRequest(BaseModel):
    kind: str
    params: dict = {}
    target_node: str = ""


class ResultRequest(BaseModel):
    order_id: str
    result: dict = {}
    error: str = ""


@router.get("/status")
def sovereign_os_status():
    hive = hive_state()
    return {"runtime": RUNTIME_VERSION, "design": DESIGN_VERSION,
            "supported_work": list(_SUPPORTED_KINDS),
            "nodes_active": hive["nodes_active"], "work": hive["work"],
            "ledger": hive["ledger"]}


@router.get("/hive")
def sovereign_os_hive():
    return hive_state()


@router.post("/work-orders")
def sovereign_os_create_order(req: OrderRequest, x_user: str = Header(default="")):
    from security.auth import authenticate
    if not authenticate(x_user):
        raise HTTPException(status_code=403, detail="owner-only: work orders "
                                                    "are issued by the owner")
    try:
        return create_work_order(req.kind, req.params, req.target_node)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/work-orders/poll")
def sovereign_os_poll(x_node_id: str = Header(default=""),
                      x_node_token: str = Header(default="")):
    return poll_work(x_node_id, x_node_token)


@router.post("/work-orders/result")
def sovereign_os_result(req: ResultRequest,
                        x_node_id: str = Header(default=""),
                        x_node_token: str = Header(default="")):
    return submit_result(x_node_id, x_node_token, req.order_id,
                         req.result, req.error)


@router.get("/work-orders")
def sovereign_os_orders(x_user: str = Header(default="")):
    from security.auth import authenticate
    if not authenticate(x_user):
        raise HTTPException(status_code=403, detail="owner-only")
    return {"orders": list(_ORDERS.values())}
