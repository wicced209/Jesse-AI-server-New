"""
CRSMCPAI Alpha - Honeypot Decoys (anti-distillation build 5)

Decoy routes on paths no legitimate visitor is ever told about:
classic scanner and prober bait (an env-file path, WordPress login
paths, debug consoles, an internal export path). Any touch is
sealed as HONEYPOT_TOUCH for the owner's review.

Rules:
- A touch returns the platform's ordinary not-found response,
  indistinguishable from any other unknown path. Nothing fake is
  served: no decoy credentials, no fabricated data - a fake secret
  published by us could be tried somewhere real, so the decoy is
  the path itself, never its contents.
- Sealing is throttled per client and path (one seal per ten
  minutes) so a scanner storm cannot flood the ledger; every touch
  is still counted in memory for the status surface.
- Clients are identified by hash only, exactly like the guard.
- Detection only: a touch never blocks the client by itself.
"""

import hashlib
import time

_seal_fn = None

BAIT_PATHS = [
    ("GET", "/.env"),
    ("GET", "/wp-admin"),
    ("GET", "/wp-login.php"),
    ("GET", "/debug"),
    ("GET", "/console"),
    ("GET", "/api/v1/admin/export"),
    ("POST", "/api/internal/ledger/export"),
]

_SEAL_WINDOW = 600
_last_sealed = {}   # (client_hash, path) -> ts
_counts = {}        # path -> {"touches": n, "seals": n}
_total_touches = 0


def set_seal_fn(fn):
    global _seal_fn
    _seal_fn = fn


def _seal(event):
    if _seal_fn is None:
        return
    try:
        _seal_fn(event)
    except Exception:
        pass


def _hash(key):
    return hashlib.sha256((key or "unknown").encode()).hexdigest()[:16]


def touch(method, path, key, now=None):
    global _total_touches
    now = time.time() if now is None else now
    ch = _hash(key)
    _total_touches += 1
    entry = _counts.setdefault(path, {"touches": 0, "seals": 0})
    entry["touches"] += 1
    marker = (ch, path)
    sealed = False
    if now - _last_sealed.get(marker, 0) >= _SEAL_WINDOW:
        _last_sealed[marker] = now
        entry["seals"] += 1
        _seal({"event": "HONEYPOT_TOUCH", "method": method,
               "path": path, "client_hash": ch})
        sealed = True
    return {"sealed": sealed}


def honeypot_status():
    return {
        "ok": True,
        "module": "honeypot",
        "bait_paths": [p for _, p in BAIT_PATHS],
        "total_touches": _total_touches,
        "by_path": dict(_counts),
        "honesty": "Decoys serve nothing fake - the ordinary "
                   "not-found response only. Touches are sealed "
                   "(throttled per client and path) for owner "
                   "review; a touch never blocks anyone by itself.",
    }
