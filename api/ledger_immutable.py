"""
CRSMCPAI Alpha - Sovereign Immutable Ledger & Audit Trail (crs.ledger.immutability)

Hash-chained, append-only ledger:
- Every entry links to the previous entry's SHA256 hash
- Genesis block anchored to the sovereign genesis hash
- Chain verification by recomputation
- Tamper detection: locate the first broken link
- Export/import of the full chain as JSON

Crash-proof guarantees:
- Standard library only (hashlib, json, time)
- NO FastAPI / web imports
- NO module-level I/O
- All methods defensive: bad input handled safely, never raises

Built per Jesse AI specification, supreme hyper immaculate God mode standards.
Owner: SLMK Jesse Martinez Junior.
"""

import hashlib
import json
import time

GENESIS_HASH = "92038cafccc7192535bd475cca985d03000d89962b8dc96f6664081663559b1b"
MAX_ENTRIES = 100000
MAX_PAYLOAD_CHARS = 65536


def _canonical(obj):
    try:
        return json.dumps(obj, sort_keys=True, separators=(",", ":"))
    except Exception:
        return ""


def compute_entry_hash(index, timestamp, payload_canonical, prev_hash):
    """SHA256 over the canonical entry fields. Never raises."""
    try:
        data = "|".join([str(index), str(timestamp), str(payload_canonical),
                         str(prev_hash), GENESIS_HASH[:16]])
        return hashlib.sha256(data.encode("utf-8")).hexdigest()
    except Exception:
        return "0" * 64


class ImmutableLedger:
    """Append-only hash-chained ledger held in memory."""

    def __init__(self, ledger_name="sovereign"):
        try:
            self.ledger_name = str(ledger_name)[:64] if ledger_name else "sovereign"
        except Exception:
            self.ledger_name = "sovereign"
        self._entries = []
        self._sealed = False

    def __len__(self):
        try:
            return len(self._entries)
        except Exception:
            return 0

    def _make_entry(self, index, payload):
        try:
            if isinstance(payload, dict):
                pl = dict(payload)
            else:
                pl = {"data": str(payload)[:MAX_PAYLOAD_CHARS]}
            canonical = _canonical(pl)[:MAX_PAYLOAD_CHARS]
        except Exception:
            pl, canonical = {}, "{}"
        ts = int(time.time())
        prev = self._entries[-1]["hash"] if self._entries else GENESIS_HASH
        return {
            "ledger": self.ledger_name,
            "index": index,
            "timestamp": ts,
            "payload": pl,
            "payload_canonical": canonical,
            "prev_hash": prev,
            "hash": compute_entry_hash(index, ts, canonical, prev),
            "genesis": GENESIS_HASH[:16],
        }

    def append_entry(self, payload):
        """Append a payload. Returns the sealed entry dict, or None if full."""
        try:
            if len(self._entries) >= MAX_ENTRIES:
                return None
            entry = self._make_entry(len(self._entries), payload)
            self._entries.append(entry)
            return dict(entry)
        except Exception:
            return None

    def get_entry(self, index):
        try:
            i = int(index)
            if 0 <= i < len(self._entries):
                return dict(self._entries[i])
            return None
        except Exception:
            return None

    def verify_chain(self):
        """Recompute every link. Returns (valid: bool, checked: int)."""
        try:
            prev = GENESIS_HASH
            for e in self._entries:
                try:
                    idx = int(e.get("index", -1))
                    ts = int(e.get("timestamp", 0))
                    pc = str(e.get("payload_canonical", ""))
                    if e.get("prev_hash") != prev:
                        return (False, idx)
                    if e.get("hash") != compute_entry_hash(idx, ts, pc, prev):
                        return (False, idx)
                    prev = e["hash"]
                except Exception:
                    return (False, -1)
            return (True, len(self._entries))
        except Exception:
            return (False, -1)

    def find_tamper_point(self):
        """Index of first broken link, or -1 if the chain is intact."""
        try:
            valid, checked = self.verify_chain()
            if valid:
                return -1
            return int(checked)
        except Exception:
            return -1

    def export_json(self):
        """Serialize the full chain to a JSON string."""
        try:
            doc = {
                "ledger": self.ledger_name,
                "genesis": GENESIS_HASH,
                "exported_at": int(time.time()),
                "entries": self._entries,
            }
            return json.dumps(doc, sort_keys=True)
        except Exception:
            return "{}"

    def import_json(self, data):
        """Replace chain contents from an export string. Returns count imported."""
        try:
            doc = json.loads(data) if isinstance(data, str) else {}
            if not isinstance(doc, dict):
                return 0
            entries = doc.get("entries")
            if not isinstance(entries, list):
                return 0
            clean = []
            for e in entries[:MAX_ENTRIES]:
                if not isinstance(e, dict):
                    continue
                try:
                    clean.append({
                        "ledger": str(e.get("ledger", self.ledger_name))[:64],
                        "index": int(e.get("index", len(clean))),
                        "timestamp": int(e.get("timestamp", 0)),
                        "payload": e.get("payload") if isinstance(e.get("payload"), dict) else {},
                        "payload_canonical": str(e.get("payload_canonical", ""))[:MAX_PAYLOAD_CHARS],
                        "prev_hash": str(e.get("prev_hash", ""))[:128],
                        "hash": str(e.get("hash", ""))[:128],
                        "genesis": str(e.get("genesis", ""))[:32],
                    })
                except Exception:
                    continue
            # re-index sequentially to keep chain coherent
            for i, e in enumerate(clean):
                e["index"] = i
            try:
                name = doc.get("ledger")
                if isinstance(name, str) and name:
                    self.ledger_name = name[:64]
            except Exception:
                pass
            self._entries = clean
            return len(clean)
        except Exception:
            return 0

    def head_hash(self):
        try:
            return self._entries[-1]["hash"] if self._entries else GENESIS_HASH
        except Exception:
            return GENESIS_HASH


def module_status():
    return {
        "module": "crs.ledger.immutability",
        "status": "ACTIVE",
        "genesis": GENESIS_HASH[:16],
        "functions": [
            "ImmutableLedger.append_entry",
            "ImmutableLedger.get_entry",
            "ImmutableLedger.verify_chain",
            "ImmutableLedger.find_tamper_point",
            "ImmutableLedger.export_json",
            "ImmutableLedger.import_json",
            "compute_entry_hash",
        ],
    }
