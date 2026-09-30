import hashlib
import json
import time

# Immutable hash-chained event ledger
_ledger_chain: list[dict] = []


def create_event(data: dict) -> dict:
    """
    Append a new event to the ledger.
    Each block is SHA3-512 chained to the previous block's hash.
    """
    previous_hash = _ledger_chain[-1]["hash"] if _ledger_chain else "GENESIS"

    payload = {
        "index":         len(_ledger_chain),
        "timestamp":     time.time(),
        "data":          data,
        "previous_hash": previous_hash,
    }

    encoded        = json.dumps(payload, sort_keys=True).encode()
    payload["hash"] = hashlib.sha3_512(encoded).hexdigest()

    _ledger_chain.append(payload)
    return payload


def get_ledger() -> list[dict]:
    """Return a copy of the full ledger chain."""
    return list(_ledger_chain)


def verify_chain() -> bool:
    """
    Walk the chain and verify every block's hash is consistent.
    Returns True if the ledger is intact, False if tampered.
    """
    for i, block in enumerate(_ledger_chain):
        stored_hash = block.pop("hash")
        recomputed  = hashlib.sha3_512(
            json.dumps(block, sort_keys=True).encode()
        ).hexdigest()
        block["hash"] = stored_hash   # restore

        if stored_hash != recomputed:
            return False

        if i > 0 and block["previous_hash"] != _ledger_chain[i - 1]["hash"]:
            return False

    return True
