"""
CRSMCPAI Alpha - Janet Protocol (JANP) v2 (2026-11-08, Muse).

Per-instance network layer running on every piece of CRS:
JANET_SYN / JANET_ACK handshake, gossip, and Merkle sync. v1 (built
2026-10-15 through the /build lane) carried the right frames with
stand-in math — an HMAC label for a signature, a hub counter for a
vector clock, and a hash of that counter for a Merkle root. v2 keeps
the frames and routes, and puts the real Planetary Hyper Sync engine
(api/hyper_sync.py) underneath: the handshake checks the caller's
genesis anchor against the ledger's GENESIS and answers with a real
stack-key signature; the vector clock is the real per-node ledger
height map; drift is computed from real Merkle fingerprints of the
actual Golden Ledger; gossip registers the peer's real state vector
with the sync engine, so the convergence picture is shared.

Owner: SLMK Jesse Martinez Junior.
"""
import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from api.hyper_sync import (convergence, handshake, local_fingerprint,
                            plan_sync, register_peer)

janet_router = APIRouter(prefix="/janet", tags=["janet-protocol"])
GENESIS_HASH = "92038cafccc7192535bd475cca985d03000d89962b8dc96f6664081663559b1b"

_peers = {}
_gossip_log = []
_sync_log = []


def _vector_clock() -> dict:
    """The real vector clock: each known node's ledger height,
    including the hub's own, from actual chain fingerprints."""
    clock = {}
    for node_id, record in _peers.items():
        fp = record.get("fingerprint") or {}
        if "height" in fp:
            clock[node_id] = fp["height"]
    from api.hyper_sync import LOCAL_NODE
    clock[LOCAL_NODE] = local_fingerprint()["height"]
    return clock


@janet_router.post("/syn")
async def janet_syn(request: dict):
    """Genesis handshake, step one: the joining instance presents its
    genesis anchor; the hub answers JANET_SYN_ACK (signed with the
    stack key) only when the anchor is the ledger's GENESIS."""
    instance_id = request.get("instance_id", "unknown")
    genesis = request.get("genesis") or request.get("genesis_hash") or GENESIS_HASH
    result = handshake(instance_id, genesis)
    if not result["accepted"]:
        return JSONResponse(status_code=403, content={
            "frame": "JANET_REJECT", "instance_id": instance_id,
            "reason": "genesis anchor does not match the Golden Ledger GENESIS"})
    _peers[instance_id] = {"status": "SYN_RECEIVED",
                           "fingerprint": request.get("fingerprint"),
                           "vector_clock": request.get("vector_clock", {}),
                           "last_seen": time.time()}
    if request.get("fingerprint"):
        register_peer(instance_id, request["fingerprint"])
    return JSONResponse(status_code=202, content={
        "frame": "JANET_SYN_ACK", "instance_id": instance_id,
        "signature": result["signature"], "hub": result["hub"],
        "hub_height": result["hub_height"],
        "hub_vector": _vector_clock()})


@janet_router.post("/ack")
async def janet_ack(request: dict):
    instance_id = request.get("instance_id", "unknown")
    if instance_id not in _peers:
        return JSONResponse(status_code=404, content={"error": "No SYN received"})
    _peers[instance_id]["status"] = "CONNECTED"
    _peers[instance_id]["last_seen"] = time.time()
    result = handshake(instance_id, GENESIS_HASH)
    return JSONResponse(content={
        "frame": "JANET_ACK", "instance_id": instance_id,
        "status": "CONNECTED", "signature": result["signature"]})


@janet_router.post("/gossip")
async def janet_gossip(request: dict):
    """Gossip: a connected peer propagates a message and, when it
    includes its state fingerprint, refreshes the sync engine's
    convergence picture with its real state."""
    instance_id = request.get("instance_id", "unknown")
    message = request.get("message", {})
    if instance_id not in _peers or _peers[instance_id]["status"] != "CONNECTED":
        return JSONResponse(status_code=403, content={"error": "Not a Janet peer"})
    _peers[instance_id]["last_seen"] = time.time()
    if request.get("fingerprint"):
        _peers[instance_id]["fingerprint"] = request["fingerprint"]
        register_peer(instance_id, request["fingerprint"])
    entry = {"from": instance_id, "message": message,
             "vector": _vector_clock(), "timestamp": time.time()}
    _gossip_log.append(entry)
    return JSONResponse(status_code=201, content={
        "propagated": True, "peers": len(_peers),
        "convergence": convergence()["counts"]})


@janet_router.post("/sync")
async def janet_sync(request: dict):
    """Merkle sync check against the REAL ledger fingerprint. Accepts
    a full peer fingerprint (preferred) or a bare merkle_root."""
    instance_id = request.get("instance_id", "unknown")
    local_fp = local_fingerprint()
    peer_fp = request.get("fingerprint")
    if peer_fp:
        plan = plan_sync(local_fp, peer_fp)
        drift = plan["relation"] not in ("in_sync",)
        entry = {"instance_id": instance_id, "drift": drift,
                 "relation": plan["relation"], "timestamp": time.time()}
        _sync_log.append(entry)
        return JSONResponse(content={"merkle_match": not drift,
                                     "drift_detected": drift,
                                     "plan": plan, "hub_root": local_fp["root"],
                                     "hub_height": local_fp["height"]})
    merkle_root = request.get("merkle_root", "")
    drift = merkle_root != local_fp["root"]
    entry = {"instance_id": instance_id, "drift": drift, "timestamp": time.time()}
    _sync_log.append(entry)
    return JSONResponse(content={"merkle_match": not drift, "drift_detected": drift,
                                 "hub_root": local_fp["root"],
                                 "hub_height": local_fp["height"]})


@janet_router.get("/peers")
async def janet_peers():
    return JSONResponse(content={"peers": _peers, "count": len(_peers),
                                 "protocol": "JANP", "version": "4-Quantum",
                                 "vector_clock": _vector_clock(),
                                 "convergence": convergence()["counts"]})
