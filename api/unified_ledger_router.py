"""
CRSMCPAI Alpha - Unified Ledger-Book Sync Router (crs.ledger.unified.sync)

The single sync spine across the four sovereign ledgers and three books:
- Dominion, Truth, Sovereign, Betrayal ledgers (api/sovereign_ledgers.py)
- Red, Black, Gray books (api/sovereign_ledgers.py, superadmin-gated)

What it does:
- Mirrors every ledger/book entry into one hash-chained sync ledger
  (SHA256 chain anchored to the sovereign genesis hash).
- Per-source watermarks: re-syncs are idempotent, only new entries sync.
- Cross-reference index: source seal -> sync entry hash.
- Chain verification by recomputation; locate first broken link.

Crash-proof guarantees:
- Standard library only (hashlib, time, json).
- NO FastAPI / web imports. NO module-level I/O.
- Zero imports from sibling modules: sources are passed in as plain dicts
  (dependency purity, 4C gate).
- All methods defensive: bad input handled safely, never raises.

Built per Jesse AI specification, supreme hyper immaculate God mode standards.
Owner: SLMK Jesse Martinez Junior.
"""

import hashlib
import json
import time

GENESIS_HASH = "92038cafccc7192535bd475cca985d03000d89962b8dc96f6664081663559b1b"

# Canonical sync sources, in fixed order for deterministic watermarking.
SOURCES = ("dominion", "truth", "sovereign", "betrayal", "red", "black", "gray")
LEDGER_SOURCES = ("dominion", "truth", "sovereign", "betrayal")
BOOK_SOURCES = ("red", "black", "gray")

MAX_ENTRIES = 100000
MAX_PAYLOAD_CHARS = 65536


def _canonical(obj):
    try:
        return json.dumps(obj, sort_keys=True, separators=(",", ":"))
    except Exception:
        return ""


def _chain_hash(index, timestamp, source, seal, prev_hash):
    """SHA256 over canonical sync-entry fields. Never raises."""
    try:
        data = "|".join([str(index), str(timestamp), str(source),
                         str(seal), str(prev_hash), GENESIS_HASH[:16]])
        return hashlib.sha256(data.encode("utf-8")).hexdigest()
    except Exception:
        return "0" * 64


class UnifiedLedgerSync:
    """Idempotent hash-chained mirror of all ledger/book entries."""

    def __init__(self):
        self._entries = []
        self._watermarks = {s: 0 for s in SOURCES}
        self._seal_index = {}  # source seal -> sync entry hash
        self._sync_runs = 0

    def __len__(self):
        try:
            return len(self._entries)
        except Exception:
            return 0

    def _seal_entry(self, source, source_entry):
        """Seal one source entry into the unified chain. Never raises."""
        try:
            if not isinstance(source_entry, dict):
                source_entry = {"data": str(source_entry)[:MAX_PAYLOAD_CHARS]}
            seal = str(source_entry.get("seal", ""))[:128]
            # Skip exact duplicates: same source + same seal already mirrored.
            key = (source, seal)
            if seal and key in self._seal_index:
                return None
            index = len(self._entries)
            ts = int(time.time())
            prev = self._entries[-1]["hash"] if self._entries else GENESIS_HASH
            payload = {
                "source": source,
                "source_seal": seal,
                "source_timestamp": str(source_entry.get("timestamp", "")),
                "data": source_entry.get("data", {}),
            }
            entry = {
                "index": index,
                "timestamp": ts,
                "source": source,
                "source_seal": seal,
                "payload_canonical": _canonical(payload)[:MAX_PAYLOAD_CHARS],
                "prev_hash": prev,
                "hash": _chain_hash(index, ts, source, seal, prev),
                "genesis": GENESIS_HASH[:16],
            }
            self._entries.append(entry)
            if seal:
                self._seal_index[key] = entry["hash"]
            return dict(entry)
        except Exception:
            return None

    def sync_source(self, source, entries_list):
        """
        Mirror all entries beyond the watermark for one source.
        entries_list: plain list of entry dicts (as stored by the source module).
        Returns number of newly synced entries. Never raises.
        """
        try:
            if source not in SOURCES:
                return 0
            if not isinstance(entries_list, (list, tuple)):
                return 0
            start = self._watermarks.get(source, 0)
            new = 0
            for entry in entries_list[start:]:
                if len(self._entries) >= MAX_ENTRIES:
                    break
                sealed = self._seal_entry(source, entry)
                if sealed is not None:
                    new += 1
            # Watermark advances past every entry we walked, even exact dupes,
            # so retries stay idempotent and never re-scan.
            self._watermarks[source] = max(start, len(entries_list))
            self._sync_runs += 1
            return new
        except Exception:
            return 0

    def sync_all(self, ledger_entries, book_entries):
        """
        Sync every source from the live sovereign_ledger module state.
        ledger_entries: dict like {"dominion": [...], ...}
        book_entries: dict like {"red": [...], ...}
        Returns {"counts": {source: n}, "total_new": n}. Never raises.
        """
        try:
            counts = {}
            total = 0
            if isinstance(ledger_entries, dict):
                for src in LEDGER_SOURCES:
                    try:
                        n = self.sync_source(src, ledger_entries.get(src, []))
                    except Exception:
                        n = 0
                    counts[src] = n
                    total += n
            if isinstance(book_entries, dict):
                for src in BOOK_SOURCES:
                    try:
                        n = self.sync_source(src, book_entries.get(src, []))
                    except Exception:
                        n = 0
                    counts[src] = n
                    total += n
            return {"counts": counts, "total_new": total}
        except Exception:
            return {"counts": {}, "total_new": 0}

    def verify_chain(self):
        """Recompute every link. Returns (valid: bool, checked: int)."""
        try:
            prev = GENESIS_HASH
            for e in self._entries:
                try:
                    idx = int(e.get("index", -1))
                    ts = int(e.get("timestamp", 0))
                    src = str(e.get("source", ""))
                    seal = str(e.get("source_seal", ""))
                    if e.get("prev_hash") != prev:
                        return (False, idx)
                    if e.get("hash") != _chain_hash(idx, ts, src, seal, prev):
                        return (False, idx)
                    prev = e["hash"]
                except Exception:
                    return (False, -1)
            return (True, len(self._entries))
        except Exception:
            return (False, -1)

    def find_tamper_point(self):
        """Index of first broken link, or -1 if intact."""
        try:
            valid, checked = self.verify_chain()
            return -1 if valid else int(checked)
        except Exception:
            return -1

    def verify_sync(self, ledger_entries, book_entries):
        """
        Check watermarks against live source counts + chain integrity.
        Returns dict. Never raises.
        """
        try:
            sources = {}
            lag = 0
            try:
                ld = ledger_entries if isinstance(ledger_entries, dict) else {}
                bk = book_entries if isinstance(book_entries, dict) else {}
                for src in LEDGER_SOURCES:
                    n = len(ld.get(src, [])) if isinstance(ld.get(src), list) else 0
                    w = self._watermarks.get(src, 0)
                    sources[src] = {"source_count": n, "watermark": w,
                                    "behind": max(0, n - w)}
                    lag += max(0, n - w)
                for src in BOOK_SOURCES:
                    n = len(bk.get(src, [])) if isinstance(bk.get(src), list) else 0
                    w = self._watermarks.get(src, 0)
                    sources[src] = {"source_count": n, "watermark": w,
                                    "behind": max(0, n - w)}
                    lag += max(0, n - w)
            except Exception:
                pass
            valid, checked = self.verify_chain()
            return {
                "chain_valid": bool(valid),
                "chain_checked": int(checked),
                "tamper_point": self.find_tamper_point(),
                "entries_behind": int(lag),
                "fully_synced": (lag == 0 and bool(valid)),
                "sources": sources,
            }
        except Exception:
            return {"chain_valid": False, "chain_checked": -1,
                    "tamper_point": -1, "entries_behind": -1,
                    "fully_synced": False, "sources": {}}

    def get_entries(self, limit=50, source=None):
        """Most recent synced entries, optionally filtered by source."""
        try:
            lim = max(1, min(int(limit), 500))
        except Exception:
            lim = 50
        try:
            src = str(source).strip().lower() if source else ""
            if src and src not in SOURCES:
                return []
            items = self._entries
            if src:
                items = [e for e in items if e.get("source") == src]
            return [dict(e) for e in items[-lim:]][::-1]
        except Exception:
            return []

    def find_by_seal(self, seal):
        """Cross-reference lookup: source seal -> synced entry. Never raises."""
        try:
            s = str(seal or "").strip()[:128]
            if not s:
                return None
            for (src, key_seal), h in self._seal_index.items():
                if key_seal == s:
                    for e in self._entries:
                        if e.get("hash") == h:
                            out = dict(e)
                            out["source"] = src
                            return out
                    return None
            return None
        except Exception:
            return None

    def head_hash(self):
        try:
            return self._entries[-1]["hash"] if self._entries else GENESIS_HASH
        except Exception:
            return GENESIS_HASH

    def status(self):
        try:
            return {
                "module": "crs.ledger.unified.sync",
                "status": "ACTIVE",
                "genesis": GENESIS_HASH[:16],
                "synced_entries": len(self),
                "head_hash": self.head_hash(),
                "watermarks": dict(self._watermarks),
                "sync_runs": int(self._sync_runs),
                "sources": list(SOURCES),
            }
        except Exception:
            return {"module": "crs.ledger.unified.sync", "status": "ERROR"}


def module_status():
    return {
        "module": "crs.ledger.unified.sync",
        "status": "ACTIVE",
        "genesis": GENESIS_HASH[:16],
        "sources": list(SOURCES),
        "owner": "SLMK Jesse Martinez Junior",
    }


def new_sync():
    """Factory: fresh UnifiedLedgerSync instance. Never raises."""
    try:
        return UnifiedLedgerSync()
    except Exception:
        return None
