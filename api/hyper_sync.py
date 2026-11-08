"""
CRSMCPAI Alpha — Planetary Hyper Sync Engine (v1, 2026-11-08, Muse).

The real synchronization engine under the name "hyper sync": the
mechanism that brings every CRS node's copy of the Golden Ledger and
its component states back into provable agreement. It implements the
Janet Protocol's recorded design with real math:

  * State vectors — each node publishes a fingerprint of its chain:
    height, genesis anchor, head hash, a Merkle root over all block
    hashes, and per-segment Merkle roots (16 blocks per segment), so
    two nodes can compare whole histories by exchanging small vectors.
  * Merkle diff reconciliation — comparing segment roots locates the
    first divergent segment; scanning that segment locates the exact
    first divergent block. No full-chain transfers to find drift.
  * Verified pull — a node behind a peer pulls only the missing tail;
    every incoming block is hash-recomputed and link-checked by the
    ledger itself (memory.ledger.import_block) before it is written.
    A forked tail (same height region, different hashes) is reported
    as FORKED and never auto-merged; a different genesis is reported
    as HISTORY_DIVERGENT and refused outright.
  * Genesis handshake — a joining node presents its genesis anchor;
    the hub answers JANET_ACK signed with the stack key when the
    anchor matches the ledger's GENESIS, JANET_REJECT otherwise.
  * Gossip — peers register their state vectors here; the engine
    continuously derives the convergence picture (who is in sync,
    behind, ahead, forked, or on a foreign history) from those real
    registered states. Propagation transport between separate
    processes rides the mesh; this registry is the comparison core.

Scope, stated plainly: this engine synchronizes ledger histories and
state vectors. Inside one process it operates on the live ledger
directly; across processes, peers exchange fingerprints and tails as
JSON through these routes. It does not invent remote nodes — the
peer table holds only states actually presented to it.

Owner: SLMK Jesse Martinez Junior.
"""
import hashlib
import json
import threading
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from core.logger import log_event

router = APIRouter(prefix="/hyper-sync", tags=["hyper-sync"])

LOCAL_NODE = "CRSMCPAI_ALPHA_CORE"
SEGMENT_SIZE = 16

_lock = threading.Lock()
_peers: Dict[str, Dict[str, Any]] = {}
_sync_events: List[Dict[str, Any]] = []


# ── Merkle math over block hashes ──────────────────────────────────────

def _combine(left: str, right: str) -> str:
    return hashlib.sha3_256(f"{left}:{right}".encode()).hexdigest()


def merkle_root(hashes: List[str]) -> str:
    if not hashes:
        return hashlib.sha3_256(b"").hexdigest()
    level = list(hashes)
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i + 1] if i + 1 < len(level) else level[i]
            nxt.append(_combine(left, right))
        level = nxt
    return level[0]


EXACT_HASH_LIMIT = 1024  # fingerprints carry full hash lists up to this height


def chain_fingerprint(blocks: List[dict]) -> Dict[str, Any]:
    """The state vector for a chain: everything two nodes need to
    compare histories without exchanging the chains themselves.
    Segment roots cover full 16-block segments only — a partial
    segment's root can never equal its completed form, so partial
    tails are compared hash-by-hash. Up to EXACT_HASH_LIMIT the full
    hash list travels with the fingerprint and diffs are exact; past
    it, diffs resolve to segment granularity and the pull itself
    (verify_tail + the ledger's link checks) is the exact arbiter."""
    from memory.ledger import GENESIS
    hashes = [b.get("block_hash") or b.get("hash") for b in blocks]
    full_segments = len(hashes) // SEGMENT_SIZE
    segments = [merkle_root(hashes[i * SEGMENT_SIZE:(i + 1) * SEGMENT_SIZE])
                for i in range(full_segments)]
    return {
        "height": len(blocks),
        "genesis": blocks[0]["prev_hash"] if blocks else GENESIS,
        "head": hashes[-1] if hashes else GENESIS,
        "root": merkle_root(hashes),
        "segments": segments,
        "tail_hashes": hashes[full_segments * SEGMENT_SIZE:],
        "hashes": hashes if len(hashes) <= EXACT_HASH_LIMIT else None,
        "segment_size": SEGMENT_SIZE,
    }


def local_fingerprint() -> Dict[str, Any]:
    from memory.ledger import get_ledger
    return chain_fingerprint(get_ledger())


def state_vector(node_id: str = LOCAL_NODE) -> Dict[str, Any]:
    fp = local_fingerprint()
    return {
        "node_id": node_id,
        "fingerprint": fp,
        "vector_clock": {node_id: fp["height"]},
        "timestamp": time.time(),
    }


# ── Diff and planning ──────────────────────────────────────────────────

def find_divergence(local_fp: Dict[str, Any], remote_fp: Dict[str, Any],
                    local_blocks: Optional[List[dict]] = None) -> Dict[str, Any]:
    """Locate the relationship between two chain fingerprints.
    Returns one of: in_sync, behind, ahead, forked (with the exact
    first divergent index whenever hash lists are available),
    history_divergent."""
    if local_fp["genesis"] != remote_fp["genesis"]:
        return {"relation": "history_divergent",
                "detail": "different genesis anchors; these are separate histories"}
    if local_fp["root"] == remote_fp["root"]:
        return {"relation": "in_sync", "detail": "Merkle roots identical"}

    # Exact path: both fingerprints carry full hash lists.
    lh, rh = local_fp.get("hashes"), remote_fp.get("hashes")
    if lh is not None and rh is not None:
        shared = min(len(lh), len(rh))
        for i in range(shared):
            if lh[i] != rh[i]:
                return {"relation": "forked", "from_index": i,
                        "segment": i // SEGMENT_SIZE,
                        "detail": f"first divergent block is index {i}"}
        if len(lh) < len(rh):
            return {"relation": "behind", "from_index": len(lh),
                    "missing": len(rh) - len(lh),
                    "detail": "local chain is a strict prefix of the remote chain"}
        return {"relation": "ahead", "by": len(lh) - len(rh),
                "detail": "remote chain is a strict prefix of the local chain"}

    # Segment path (large chains): full segments compare exactly.
    shared_segments = min(len(local_fp["segments"]), len(remote_fp["segments"]))
    for s in range(shared_segments):
        if local_fp["segments"][s] != remote_fp["segments"][s]:
            return {"relation": "forked", "segment": s,
                    "from_index": s * SEGMENT_SIZE,
                    "detail": f"histories diverge inside segment {s}; the pull "
                              f"itself verifies the exact block"}
    # All shared full segments match. Compare the tails hash-by-hash
    # where they overlap in absolute index space.
    base = shared_segments * SEGMENT_SIZE
    lt = local_fp.get("tail_hashes") or []
    rt = remote_fp.get("tail_hashes") or []
    # Tails begin at each chain's own full-segment boundary; align by
    # absolute index using heights.
    local_tail_start = local_fp["height"] - len(lt)
    remote_tail_start = remote_fp["height"] - len(rt)
    if local_tail_start == remote_tail_start:
        for i in range(min(len(lt), len(rt))):
            if lt[i] != rt[i]:
                return {"relation": "forked", "from_index": local_tail_start + i,
                        "segment": (local_tail_start + i) // SEGMENT_SIZE,
                        "detail": f"first divergent block is index {local_tail_start + i}"}
    if local_fp["height"] < remote_fp["height"]:
        return {"relation": "behind", "from_index": local_fp["height"],
                "missing": remote_fp["height"] - local_fp["height"],
                "detail": "shared history agrees over every comparable "
                          "segment and tail hash; the pull verifies the rest"}
    if local_fp["height"] > remote_fp["height"]:
        return {"relation": "ahead", "by": local_fp["height"] - remote_fp["height"],
                "detail": "shared history agrees over every comparable segment"}
    return {"relation": "forked", "from_index": base,
            "segment": base // SEGMENT_SIZE,
            "detail": "equal heights, different roots, divergence in the "
                      "incomparable tail region; segment located"}


def plan_sync(local_fp: Dict[str, Any], remote_fp: Dict[str, Any],
              local_blocks: Optional[List[dict]] = None) -> Dict[str, Any]:
    plan = find_divergence(local_fp, remote_fp, local_blocks)
    plan["local_height"] = local_fp["height"]
    plan["remote_height"] = remote_fp["height"]
    if plan["relation"] == "behind":
        plan["action"] = "pull_tail"
    elif plan["relation"] == "ahead":
        plan["action"] = "offer_tail"
    elif plan["relation"] == "in_sync":
        plan["action"] = "none"
    elif plan["relation"] == "forked":
        plan["action"] = "hold_for_owner"
    else:
        plan["action"] = "refuse"
    return plan


# ── Verified pull ──────────────────────────────────────────────────────

def verify_tail(blocks_tail: List[dict], expected_prev: str) -> tuple:
    """Recompute every incoming block's hash and check the linkage,
    in order, before anything is written. Returns (ok, reason)."""
    prev = expected_prev
    for block in blocks_tail:
        check = {k: v for k, v in block.items() if k not in ("block_hash", "hash")}
        expected = hashlib.sha3_512(
            json.dumps(check, sort_keys=True).encode()).hexdigest()
        if block.get("block_hash") != expected:
            return False, f"block {block.get('index')} hash does not recompute"
        if block.get("prev_hash") != prev:
            return False, f"block {block.get('index')} does not link to its predecessor"
        prev = block["block_hash"]
    return True, "verified"


def reconcile(blocks_tail: List[dict]) -> Dict[str, Any]:
    """Pull a verified tail into the live ledger. All-or-nothing:
    the whole tail verifies first; only then is it imported, block by
    block, through the ledger's own guarded import path."""
    from memory.ledger import get_ledger, import_block, verify_chain
    chain = get_ledger()
    if not blocks_tail:
        return {"imported": 0, "status": "nothing_to_pull"}
    if blocks_tail[0].get("index") != len(chain):
        return {"imported": 0, "status": "refused",
                "reason": f"tail starts at index {blocks_tail[0].get('index')}, "
                          f"local height is {len(chain)}"}
    expected_prev = chain[-1]["block_hash"] if chain else blocks_tail[0]["prev_hash"]
    ok, reason = verify_tail(blocks_tail, expected_prev)
    if not ok:
        return {"imported": 0, "status": "refused", "reason": reason}
    imported = 0
    for block in blocks_tail:
        if not import_block(block):
            return {"imported": imported, "status": "halted",
                    "reason": f"ledger refused block {block.get('index')} mid-import"}
        imported += 1
    valid = verify_chain()
    event = {"action": "reconcile", "imported": imported, "chain_valid": valid,
             "timestamp": time.time()}
    with _lock:
        _sync_events.append(event)
    log_event(f"[HYPER-SYNC] reconciled {imported} blocks; chain valid: {valid}")
    return {"imported": imported, "status": "converged" if valid else "imported_but_chain_invalid",
            "chain_valid": valid, "new_height": len(chain) + imported}


# ── Genesis handshake + peer registry (gossip core) ────────────────────

def handshake(node_id: str, genesis: str) -> Dict[str, Any]:
    from memory.ledger import GENESIS
    from security.crypto import sign_data
    accepted = genesis == GENESIS
    payload = f"JANET:{node_id}:{genesis}:{int(time.time())}"
    return {
        "frame": "JANET_ACK" if accepted else "JANET_REJECT",
        "node_id": node_id,
        "accepted": accepted,
        "hub": LOCAL_NODE,
        "hub_height": local_fingerprint()["height"],
        "signature": sign_data(payload.encode()),
    }


def register_peer(node_id: str, fingerprint: Dict[str, Any]) -> Dict[str, Any]:
    with _lock:
        _peers[node_id] = {"fingerprint": fingerprint, "last_seen": time.time()}
    return convergence()


def convergence() -> Dict[str, Any]:
    """The gossip picture, derived only from states actually
    registered: how every known peer stands against the local chain."""
    local_fp = local_fingerprint()
    picture = {}
    with _lock:
        peers = dict(_peers)
    for node_id, record in peers.items():
        picture[node_id] = plan_sync(local_fp, record["fingerprint"])
    counts = {"in_sync": 0, "behind": 0, "ahead": 0, "forked": 0, "history_divergent": 0}
    for plan in picture.values():
        counts[plan["relation"]] = counts.get(plan["relation"], 0) + 1
    return {
        "local_node": LOCAL_NODE,
        "local_height": local_fp["height"],
        "local_root": local_fp["root"],
        "peers": len(peers),
        "counts": counts,
        "picture": picture,
        "sync_events": len(_sync_events),
    }


# ── Routes ─────────────────────────────────────────────────────────────

class PeerState(BaseModel):
    node_id: str
    fingerprint: Dict[str, Any]


class HandshakeRequest(BaseModel):
    node_id: str
    genesis: str


class PlanRequest(BaseModel):
    fingerprint: Dict[str, Any]


class ReconcileRequest(BaseModel):
    blocks: List[Dict[str, Any]]


@router.get("/state")
def hyper_sync_state():
    return state_vector()


@router.post("/handshake")
def hyper_sync_handshake(req: HandshakeRequest):
    return handshake(req.node_id, req.genesis)


@router.post("/peer")
def hyper_sync_peer(req: PeerState):
    return register_peer(req.node_id, req.fingerprint)


@router.post("/plan")
def hyper_sync_plan(req: PlanRequest):
    from memory.ledger import get_ledger
    return plan_sync(local_fingerprint(), req.fingerprint, get_ledger())


@router.post("/reconcile")
def hyper_sync_reconcile(req: ReconcileRequest):
    return reconcile(req.blocks)


@router.get("/status")
def hyper_sync_status():
    return convergence()
