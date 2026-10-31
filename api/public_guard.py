"""
CRSMCPAI Alpha - Public Surface Guard (anti-distillation build 2)

Rate and window limits for the public lanes — the surfaces a stranger
can reach without identity. The demo lane is the real harvesting
surface: it hands full answers to anyone. Humans ask a handful of
questions; harvesters ask thousands on a schedule. This module counts
per client per lane over a sliding window and refuses past the limit.

Design rules:
- Client key = first X-Forwarded-For entry when present (the service
  sits behind the platform proxy), else the direct peer address.
- Only a HASH of the client key is ever sealed or shown. Correlation
  across alerts works; raw addresses never enter the immutable record.
- A breach seals one PUBLIC_GUARD_ALERT per client+lane+window (not
  one per refused request) naming the lane, the count, and the limit.
- The owner can clear a client instantly (reset) — a false positive
  must never lock out a real visitor for long. Limits also expire
  with the window on their own.
- Authenticated owner traffic never passes through this module.

State is in-memory and resets on restart, like the sibling modules;
the alerts persist as ledger seals.
"""

import hashlib
import time
from collections import deque

_seal_fn = None

WINDOW_SECONDS = 600          # 10-minute sliding window
LANE_LIMITS = {
    "demo": 40,               # full-answer commands per window per client
    "demo_event": 240,        # analytics events per window per client
}
_DEFAULT_LIMIT = 120

_HITS = {}                    # (lane, client_hash) -> deque[timestamps]
_BREACH_SEALED = {}           # (lane, client_hash) -> window id last sealed
_ALERTS = 0
_REFUSALS = 0


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


def client_key(request):
    """Best client identity for counting: first XFF entry, else peer."""
    try:
        xff = request.headers.get("x-forwarded-for", "")
        if xff:
            first = xff.split(",")[0].strip()
            if first:
                return first
        if request.client and request.client.host:
            return request.client.host
    except Exception:
        pass
    return "unknown"


def client_hash(key):
    return hashlib.sha256((key or "unknown").encode()).hexdigest()[:16]


def check(lane, key, now=None):
    """Record one hit. Returns {"allowed": bool, "count": n, "limit": m}.
    Seals a PUBLIC_GUARD_ALERT on the first refusal in a window."""
    global _ALERTS, _REFUSALS
    now = time.time() if now is None else now
    limit = LANE_LIMITS.get(lane, _DEFAULT_LIMIT)
    ch = client_hash(key)
    bucket = _HITS.setdefault((lane, ch), deque())
    cutoff = now - WINDOW_SECONDS
    while bucket and bucket[0] < cutoff:
        bucket.popleft()
    bucket.append(now)
    count = len(bucket)
    if count <= limit:
        return {"allowed": True, "count": count, "limit": limit}
    _REFUSALS += 1
    window_id = int(now // WINDOW_SECONDS)
    if _BREACH_SEALED.get((lane, ch)) != window_id:
        _BREACH_SEALED[(lane, ch)] = window_id
        _ALERTS += 1
        _seal({"event": "PUBLIC_GUARD_ALERT", "lane": lane,
               "client_hash": ch, "count": count, "limit": limit,
               "window_seconds": WINDOW_SECONDS})
    return {"allowed": False, "count": count, "limit": limit}


def reset_client(lane, key):
    ch = client_hash(key)
    existed = _HITS.pop((lane, ch), None) is not None
    _BREACH_SEALED.pop((lane, ch), None)
    return {"ok": True, "lane": lane, "client_hash": ch,
            "cleared": existed}


def guard_status():
    now = time.time()
    cutoff = now - WINDOW_SECONDS
    active = {}
    for (lane, ch), bucket in _HITS.items():
        n = sum(1 for t in bucket if t >= cutoff)
        if n:
            active.setdefault(lane, []).append(
                {"client_hash": ch, "count": n,
                 "limit": LANE_LIMITS.get(lane, _DEFAULT_LIMIT)})
    return {
        "ok": True,
        "module": "public_guard",
        "window_seconds": WINDOW_SECONDS,
        "lane_limits": dict(LANE_LIMITS, default=_DEFAULT_LIMIT),
        "active_clients": active,
        "alerts_sealed_this_boot": _ALERTS,
        "refusals_this_boot": _REFUSALS,
        "honesty": "Counts are per hashed client key over a sliding "
                   "window, in memory; they reset on restart. Breach "
                   "alerts persist as ledger seals. Raw client "
                   "addresses are never sealed or shown.",
    }
