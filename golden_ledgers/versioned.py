"""
Versioned Golden Ledgers V23–V27.
Pattern follows V28 (SHA3-512 hash chain, append-only, owner-sealed).
Owner: SLMK Jesse Martinez Junior
"""
import hashlib
import json
import os
import time
from core.config import SOVEREIGN_OWNER
from core.logger import log_event

GENESIS = "92038cafccc7192535bd475cca985d03000d89962b8dc96f6664081663559b1b"
BASE = os.path.dirname(__file__)


class GoldenLedgerVersioned:
    def __init__(self, version: str):
        self.version = version
        self.owner = SOVEREIGN_OWNER
        self.path = os.path.join(BASE, f"golden_ledger_{version}.json")
        self._chain = self._load()
        if not self._chain:
            # Genesis block. The hash must be computed over the exact
            # stored payload (owner included) or verify() can never pass;
            # the sandbox original hashed a smaller dict. Fixed by Muse
            # 2026-11-06 after the verification battery caught it.
            genesis_payload = {"event": "GENESIS", "version": version, "owner": self.owner}
            self._chain = [{
                "index": 0,
                "ts": time.time(),
                "owner": self.owner,
                "payload": genesis_payload,
                "prev_hash": GENESIS,
                "block_hash": self._hash(0, GENESIS, genesis_payload),
            }]
            self._save()
        log_event(f"[GOLDEN_LEDGER_{version}] loaded blocks={len(self._chain)}")

    def _hash(self, index, prev, payload) -> str:
        body = f"{index}|{prev}|{json.dumps(payload, sort_keys=True)}|{self.owner}"
        return hashlib.sha3_512(body.encode()).hexdigest()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path) as f:
                    data = json.load(f)
                    return data if isinstance(data, list) else []
            except Exception:
                return []
        return []

    def _save(self):
        with open(self.path, "w") as f:
            json.dump(self._chain, f, indent=2)

    def append(self, payload: dict) -> dict:
        prev = self._chain[-1]["block_hash"]
        idx = len(self._chain)
        block = {
            "index": idx,
            "ts": time.time(),
            "owner": self.owner,
            "payload": payload,
            "prev_hash": prev,
            "block_hash": self._hash(idx, prev, payload),
        }
        self._chain.append(block)
        self._save()
        return block

    def verify(self) -> dict:
        if not self._chain:
            return {"valid": False, "reason": "empty"}
        for i, b in enumerate(self._chain):
            if i == 0:
                if b["prev_hash"] != GENESIS:
                    return {"valid": False, "reason": "genesis mismatch", "index": 0}
            else:
                if b["prev_hash"] != self._chain[i - 1]["block_hash"]:
                    return {"valid": False, "reason": "chain break", "index": i}
            expected = self._hash(b["index"], b["prev_hash"], b["payload"])
            if expected != b["block_hash"]:
                return {"valid": False, "reason": "hash mismatch", "index": i}
        return {"valid": True, "blocks": len(self._chain), "version": self.version}

    def status(self) -> dict:
        v = self.verify()
        return {
            "version": self.version,
            "owner": self.owner,
            "blocks": len(self._chain),
            "chain_valid": v.get("valid", False),
            "path": self.path,
            "status": "LIVE",
        }


LEDGERS = {
    "V23": GoldenLedgerVersioned("V23"),
    "V24": GoldenLedgerVersioned("V24"),
    "V25": GoldenLedgerVersioned("V25"),
    "V26": GoldenLedgerVersioned("V26"),
    "V27": GoldenLedgerVersioned("V27"),
}


def ledger_status() -> dict:
    return {
        "family": "GOLDEN_LEDGER_VERSIONED",
        "owner": SOVEREIGN_OWNER,
        "versions": {k: v.status() for k, v in LEDGERS.items()},
        "primary_live": "V28 (memory/ledger.py)",
        "status": "LIVE",
    }
