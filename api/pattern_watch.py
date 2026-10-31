"""
CRSMCPAI Alpha - Harvest Pattern Watch (anti-distillation build 3)

Detection layer over the public lanes. The rate guard (build 2) caps
volume; this module watches the SHAPE of traffic for harvesting and
probing behavior and seals an alert when the shape is wrong:

- metronome: many hits at near-identical intervals (machine cadence)
- burst: a dense cluster inside one minute
- repetition: the same command asked again and again (probe looping)
- enumeration: many distinct short probes in one window (sweeping)

Rules:
- Detection NEVER blocks and never punishes. It seals
  HARVEST_PATTERN_ALERT for the owner's review. Bans stay an owner
  act (a spoofed signal must not be able to frame a real visitor).
  Because an alert costs only a line in the owner's review list, the
  metronome line is deliberately sensitive: a steady cadence sweep
  is worth a glance even when it might be an unusually regular human.
- Clients are tracked by hash only, exactly like the guard.
- One alert per client per window per signal set; the alert names
  the signals and the score, never the command text itself (only a
  short fingerprint of it is kept, for repetition counting).

State is in-memory (per-client rings, capped) and resets on restart;
alerts persist as ledger seals.
"""

import hashlib
import statistics
import time
from collections import deque

_seal_fn = None

WINDOW_SECONDS = 600
RING_MAX = 200
ALERT_THRESHOLD = 50

SIGNAL_POINTS = {"metronome": 40, "burst": 30,
                 "repetition": 30, "enumeration": 20}

_RINGS = {}        # client_hash -> deque of (ts, fingerprint, length)
_ALERTED = {}      # client_hash -> (window_id, frozenset(signals))
_ALERTS = []       # in-memory mirror of sealed alerts this boot


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


def _fingerprint(text):
    words = " ".join((text or "").lower().split()[:8])
    return hashlib.sha256(words.encode()).hexdigest()[:12]


def _signals(events, now):
    """events: list of (ts, fingerprint, length) inside the window."""
    found = {}
    n = len(events)
    if n >= 10:
        times = [e[0] for e in events]
        gaps = [b - a for a, b in zip(times, times[1:])]
        if gaps:
            mean = statistics.mean(gaps)
            if mean > 0:
                stdev = statistics.pstdev(gaps) if len(gaps) > 1 else 0.0
                # Near-exact cadence only (CV under 0.10): a jittered
                # human rhythm varies far more than a sleep loop does.
                if stdev / mean < 0.10:
                    found["metronome"] = {
                        "hits": n, "mean_gap_s": round(mean, 2)}
    if n >= 25:
        times = sorted(e[0] for e in events)
        for i, t in enumerate(times):
            j = i
            while j < n and times[j] - t <= 60:
                j += 1
            if j - i >= 25:
                found["burst"] = {"hits_in_60s": j - i}
                break
    fps = {}
    for _, fp, _ in events:
        fps[fp] = fps.get(fp, 0) + 1
    top = max(fps.values()) if fps else 0
    if top >= 6:
        found["repetition"] = {"same_command_count": top}
    if len(fps) >= 20:
        lengths = sorted(e[2] for e in events)
        median = lengths[len(lengths) // 2]
        if median < 40:
            found["enumeration"] = {"distinct_commands": len(fps),
                                    "median_length": median}
    return found


def observe(lane, key, text, now=None):
    """Record one public-lane request and evaluate its shape.
    Returns {"score": int, "signals": {...}, "alerted": bool}."""
    now = time.time() if now is None else now
    ch = _hash(key)
    ring = _RINGS.setdefault(ch, deque(maxlen=RING_MAX))
    ring.append((now, _fingerprint(text), len(text or "")))
    cutoff = now - WINDOW_SECONDS
    events = [e for e in ring if e[0] >= cutoff]
    found = _signals(events, now)
    score = sum(SIGNAL_POINTS[s] for s in found)
    alerted = False
    if score >= ALERT_THRESHOLD:
        window_id = int(now // WINDOW_SECONDS)
        marker = (window_id, frozenset(found))
        if _ALERTED.get(ch) != marker:
            _ALERTED[ch] = marker
            alert = {"event": "HARVEST_PATTERN_ALERT", "lane": lane,
                     "client_hash": ch, "score": score,
                     "signals": {k: v for k, v in found.items()}}
            _ALERTS.append(alert)
            del _ALERTS[:-50]
            _seal(alert)
            alerted = True
    return {"score": score, "signals": found, "alerted": alerted}


def watch_status():
    return {
        "ok": True,
        "module": "pattern_watch",
        "window_seconds": WINDOW_SECONDS,
        "alert_threshold": ALERT_THRESHOLD,
        "signal_points": dict(SIGNAL_POINTS),
        "clients_tracked": len(_RINGS),
        "alerts_this_boot": len(_ALERTS),
        "recent_alerts": list(_ALERTS[-10:]),
        "honesty": "Detection only: nothing is blocked or banned by "
                   "this module. Alerts are sealed for owner review; "
                   "any ban is a separate owner act. Clients are "
                   "tracked by hash; command text is never stored, "
                   "only a short fingerprint for repetition counting.",
    }
