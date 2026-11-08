"""
CRSMCPAI Alpha — Black Swarm (v1, 2026-11-08, Muse).

Built from the recovered spec (the recovery record marks Black Swarm
EXISTENCE UNCONFIRMED — described logic only, no module code anywhere
we hold). The spec, decoded in MYTHOS_DECODE_WORKING.md and the
Guardian Ecosystem rules:

  "Black Swarm Nodes: Decentralized Edge Mesh... Maintaining
   redundant communication routing paths to prevent node isolation."
  "Black Swarm coordinates defensive responses only."

So this module is three real mechanisms over an edge-node registry:

  1. REGISTRY — swarm nodes enroll with a heartbeat; a node whose
     heartbeat ages past NODE_TTL is marked stale (never silently
     dropped from the record).
  2. REDUNDANT ROUTING — route_plan(destination) returns a primary
     path plus backup paths through distinct active nodes, so no
     single node failure isolates the destination. When fewer than
     two active nodes exist it says so plainly (redundancy: False)
     instead of pretending.
  3. DEFENSIVE COORDINATION — coordinate(alert) broadcasts ONE
     defensive directive to every active node (HEIGHTENED_WATCH for
     high severity, ISOLATE_SOURCE for critical, naming the flagged
     source), records the broadcast, and tracks node acknowledgments.
     Defensive only: the swarm issues watch/isolate directives; it
     executes nothing against any external system.

State is in-process, like the mesh registry it complements; directive
broadcasts are sealed to the ledger on a best-effort basis.
"""
import threading
import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from core.logger import log_event

OWNER = "jesse_martinez_jr"
NODE_TTL = 300.0  # seconds without a heartbeat before a node is stale


class BlackSwarm:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._nodes: dict = {}        # node_id -> {enrolled, last_seen, isolated}
        self._directives: list = []   # broadcast record
        self._acks: dict = {}         # directive_id -> {node_id: ts}
        self._directive_counter = 0

    # ── registry ───────────────────────────────────────────────────────
    def enroll(self, node_id: str) -> dict:
        with self._lock:
            node = self._nodes.setdefault(
                node_id, {"enrolled": time.time(), "isolated": False})
            node["last_seen"] = time.time()
            return {"node": node_id, "enrolled": True}

    def heartbeat(self, node_id: str) -> dict:
        with self._lock:
            node = self._nodes.get(node_id)
            if node is None:
                return {"node": node_id, "known": False}
            node["last_seen"] = time.time()
            return {"node": node_id, "known": True}

    def _active_nodes(self, now: float) -> list:
        return [nid for nid, n in self._nodes.items()
                if not n["isolated"] and now - n["last_seen"] <= NODE_TTL]

    # ── redundant routing ──────────────────────────────────────────────
    def route_plan(self, destination: str, now: float = None) -> dict:
        now = now if now is not None else time.time()
        with self._lock:
            active = self._active_nodes(now)
            paths = [[nid, destination] for nid in active]
            return {
                "destination": destination,
                "paths": paths,
                "primary": paths[0] if paths else None,
                "backups": paths[1:],
                "redundancy": len(paths) >= 2,
                "active_nodes": len(active),
                "note": (None if len(paths) >= 2 else
                         "fewer than two active nodes — no redundant path exists"),
            }

    # ── defensive coordination ─────────────────────────────────────────
    def coordinate(self, alert: dict, now: float = None) -> dict:
        now = now if now is not None else time.time()
        severity = str(alert.get("severity") or "medium")
        source = str(alert.get("source") or "unknown")
        directive_kind = "ISOLATE_SOURCE" if severity == "critical" else "HEIGHTENED_WATCH"
        with self._lock:
            self._directive_counter += 1
            directive = {
                "id": self._directive_counter,
                "kind": directive_kind,
                "target_source": source,
                "rule": alert.get("rule"),
                "severity": severity,
                "issued": now,
                "recipients": self._active_nodes(now),
            }
            if directive_kind == "ISOLATE_SOURCE" and source in self._nodes:
                self._nodes[source]["isolated"] = True
                directive["isolated_node"] = source
            self._directives.append(directive)
            self._acks[directive["id"]] = {}
        log_event(f"[BLACK SWARM] directive {directive['id']} {directive_kind} "
                  f"-> {len(directive['recipients'])} nodes (source={source})", "warning")
        try:
            from memory.ledger import create_event
            create_event({"module": "BLACK_SWARM", "event": "DIRECTIVE",
                          "directive_id": directive["id"], "kind": directive_kind,
                          "target_source": source})
        except Exception:
            pass
        return directive

    def acknowledge(self, directive_id: int, node_id: str) -> dict:
        with self._lock:
            acks = self._acks.get(directive_id)
            if acks is None:
                return {"directive": directive_id, "known": False}
            acks[node_id] = time.time()
            return {"directive": directive_id, "known": True,
                    "acks": len(acks)}

    def status(self, now: float = None) -> dict:
        now = now if now is not None else time.time()
        with self._lock:
            active = self._active_nodes(now)
            return {
                "module": "BLACK_SWARM",
                "version": "v1 (built 2026-11-08)",
                "role": "decentralized edge mesh — redundant routing, defensive coordination only",
                "nodes_total": len(self._nodes),
                "nodes_active": len(active),
                "nodes_isolated": sum(1 for n in self._nodes.values() if n["isolated"]),
                "directives_issued": len(self._directives),
                "last_directive": self._directives[-1] if self._directives else None,
            }


black_swarm = BlackSwarm()

black_swarm_router = APIRouter(prefix="/black-swarm", tags=["black-swarm"])


@black_swarm_router.post("/enroll")
async def swarm_enroll(request: dict):
    return JSONResponse(content=black_swarm.enroll(str(request.get("node") or "")))


@black_swarm_router.post("/heartbeat")
async def swarm_heartbeat(request: dict):
    return JSONResponse(content=black_swarm.heartbeat(str(request.get("node") or "")))


@black_swarm_router.get("/route")
async def swarm_route(destination: str = ""):
    return JSONResponse(content=black_swarm.route_plan(destination))


@black_swarm_router.post("/respond")
async def swarm_respond(request: dict):
    if str(request.get("user") or "") != OWNER:
        return JSONResponse(status_code=403, content={
            "allowed": False, "reason": "swarm coordination is owner-only"})
    return JSONResponse(content=black_swarm.coordinate(request.get("alert") or {}))


@black_swarm_router.post("/ack")
async def swarm_ack(request: dict):
    return JSONResponse(content=black_swarm.acknowledge(
        int(request.get("directive") or 0), str(request.get("node") or "")))


@black_swarm_router.get("/status")
async def swarm_status():
    return JSONResponse(content=black_swarm.status())
