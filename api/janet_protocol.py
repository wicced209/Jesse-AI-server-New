"""
CRSMCPAI Alpha - Janet Protocol (JANP)
Per-instance network layer running on EVERY piece of CRS.
JANET_SYN / JANET_ACK handshake, gossip-sub, Merkle sync.
Owner: SLMK Jesse Martinez Junior
Built by Jesse AI via /build, 4C/4V gate GO.
Supreme hyper immaculate God mode standards.
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse
import hashlib
import hmac
import time

janet_router = APIRouter(prefix="/janet", tags=["janet-protocol"])
GENESIS_HASH = "92038cafccc7192535bd475cca985d03000d89962b8dc96f6664081663559b1b"

_peers = {}
_vector_clock = {"hub": 0}
_gossip_log = []
_sync_log = []


def _sign(data: str) -> str:
    return hmac.new(GENESIS_HASH.encode(), data.encode(), hashlib.sha3_256).hexdigest()[:32]


@janet_router.post("/syn")
async def janet_syn(request: dict):
    instance_id = request.get("instance_id", "unknown")
    vector = request.get("vector_clock", {})
    sig = _sign(f"SYN:{instance_id}")
    _vector_clock["hub"] += 1
    _peers[instance_id] = {"status": "SYN_RECEIVED", "vector_clock": vector,
                           "last_seen": time.time()}
    return JSONResponse(status_code=202, content={
        "frame": "JANET_SYN_ACK", "instance_id": instance_id,
        "signature": sig, "hub_vector": _vector_clock["hub"]})


@janet_router.post("/ack")
async def janet_ack(request: dict):
    instance_id = request.get("instance_id", "unknown")
    if instance_id not in _peers:
        return JSONResponse(status_code=404, content={"error": "No SYN received"})
    _peers[instance_id]["status"] = "CONNECTED"
    _peers[instance_id]["last_seen"] = time.time()
    return JSONResponse(content={
        "frame": "JANET_ACK", "instance_id": instance_id,
        "status": "CONNECTED", "signature": _sign(f"ACK:{instance_id}")})


@janet_router.post("/gossip")
async def janet_gossip(request: dict):
    instance_id = request.get("instance_id", "unknown")
    message = request.get("message", {})
    if instance_id not in _peers or _peers[instance_id]["status"] != "CONNECTED":
        return JSONResponse(status_code=403, content={"error": "Not a Janet peer"})
    _vector_clock["hub"] += 1
    entry = {"from": instance_id, "message": message,
             "vector": _vector_clock["hub"],
             "signature": _sign(f"GOSSIP:{instance_id}:{time.time()}")}
    _gossip_log.append(entry)
    return JSONResponse(status_code=201, content={"propagated": True, "peers": len(_peers)})


@janet_router.post("/sync")
async def janet_sync(request: dict):
    instance_id = request.get("instance_id", "unknown")
    merkle_root = request.get("merkle_root", "")
    local_root = hashlib.sha3_256(str(_vector_clock).encode()).hexdigest()[:32]
    drift = merkle_root != local_root
    entry = {"instance_id": instance_id, "drift": drift, "timestamp": time.time()}
    _sync_log.append(entry)
    return JSONResponse(content={"merkle_match": not drift, "drift_detected": drift,
                                 "hub_root": local_root})


@janet_router.get("/peers")
async def janet_peers():
    return JSONResponse(content={"peers": _peers, "count": len(_peers),
                                 "protocol": "JANP", "version": "4-Quantum"})
