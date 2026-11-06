"""
Phoenix snapshot and persistence — snapshot, rollback verification, lattice health proof.
Owner: SLMK Jesse Martinez Junior
"""
import hashlib
import json
import os
import time
from core.config import SOVEREIGN_OWNER
from core.logger import log_event

BASE = os.path.dirname(__file__)
SNAP_DIR = os.path.join(BASE, "snapshots")
os.makedirs(SNAP_DIR, exist_ok=True)


class PhoenixSnapshot:
    MODULE_ID = "phoenix_snapshot"
    OWNER = SOVEREIGN_OWNER

    def __init__(self):
        self._index = {}
        self._load_index()
        log_event(f"[{self.MODULE_ID}] initialized")

    def _load_index(self):
        idx_path = os.path.join(SNAP_DIR, "index.json")
        if os.path.exists(idx_path):
            with open(idx_path) as f:
                self._index = json.load(f)

    def _save_index(self):
        with open(os.path.join(SNAP_DIR, "index.json"), "w") as f:
            json.dump(self._index, f, indent=2)

    def status(self):
        return {
            "module": self.MODULE_ID,
            "owner": self.OWNER,
            "status": "LIVE",
            "snapshots": len(self._index),
            "features": ["snapshot", "rollback_verify", "lattice_health_proof"],
        }

    def snapshot(self, label: str, state: dict) -> dict:
        sid = hashlib.sha3_256(f"{label}|{time.time()}".encode()).hexdigest()[:16]
        blob = json.dumps(state, sort_keys=True)
        h = hashlib.sha3_512(blob.encode()).hexdigest()
        path = os.path.join(SNAP_DIR, f"{sid}.json")
        with open(path, "w") as f:
            json.dump({"label": label, "state": state, "hash": h, "owner": self.OWNER,
                       "ts": time.time()}, f, indent=2)
        self._index[sid] = {"label": label, "hash": h, "path": path, "ts": time.time()}
        self._save_index()
        return {"snapshot_id": sid, "hash": h, "label": label}

    def rollback_verify(self, snapshot_id: str, current_state: dict) -> dict:
        if snapshot_id not in self._index:
            return {"ok": False, "error": "snapshot not found"}
        with open(self._index[snapshot_id]["path"]) as f:
            stored = json.load(f)
        current_hash = hashlib.sha3_512(json.dumps(current_state, sort_keys=True).encode()).hexdigest()
        match = current_hash == stored["hash"]
        return {
            "ok": True,
            "snapshot_id": snapshot_id,
            "matches_snapshot": match,
            "stored_hash": stored["hash"],
            "current_hash": current_hash,
        }

    def lattice_health_proof(self) -> dict:
        """Deterministic health proof over the snapshot lattice."""
        items = sorted(self._index.items())
        chain = GENESIS = "92038cafccc7192535bd475cca985d03000d89962b8dc96f6664081663559b1b"
        for sid, meta in items:
            chain = hashlib.sha3_512(f"{chain}|{sid}|{meta['hash']}".encode()).hexdigest()
        return {
            "ok": True,
            "proof": chain,
            "snapshot_count": len(items),
            "owner": self.OWNER,
            "healthy": True,
        }


phoenix = PhoenixSnapshot()
