"""
Telemetry ingestion intake — CRSMCPAI Alpha data-pull groundwork.

Spec source: Jesse AI's execution-66 gap list (2026-10-30): the
data-pull ingestion path is unwritten, and the overnight review found
the telemetry bridge daemons unimplemented. In the owner's
architecture this intake is the receiving end of the CRS router:
telemetry returns to CRSMCPAI Alpha through a guarded door, or it
does not return at all.

Design:
  - Sources enroll (owner action) and receive a source secret, shown
    exactly once. The server stores only SHA3-512(secret), the same
    construction as the trusted device registry.
  - Every batch is signed: HMAC-SHA3-512(key = SHA3-512(secret),
    message = canonical batch body + timestamp). Batches carry a
    per-source sequence number that must strictly increase, which
    kills replays and reordering. Timestamps must sit within a
    five-minute window.
  - Validation is total before acceptance: known source, active
    state, fresh timestamp, correct signature, sequence advancing,
    shape limits (at most 100 events per batch, each event an object
    with a string kind).
  - Accepted batches are fingerprinted (SHA3-512 of the canonical
    events) and sealed: the seal carries source, sequence, event
    count, and fingerprint — the audit trail proves what arrived and
    when, without copying payload contents into the record.
  - Recent batches (last 50) are held in a bounded in-memory ring for
    the owner's inspection. Nothing else is retained; this module is
    the door and the logbook, not the warehouse. The 4.2 PB data
    restoration itself rides on sources actually connecting, which
    has not happened yet — connected_sources is zero and the status
    says so.

Rejected batches are counted by reason, so a failing source is
visible instead of silent.
"""

import hashlib
import hmac
import json
import secrets
import time
import uuid

OWNER = "SLMK Jesse Martinez Junior"
MAX_EVENTS_PER_BATCH = 100
TIMESTAMP_WINDOW = 300  # seconds
RING_SIZE = 50

_SOURCES = {}     # source_id -> record (secret only as SHA3-512)
_RING = []        # recent accepted batches, bounded
_REJECTS = {}     # reason -> count
_EVENTS = []      # in-memory mirror of sealed events

_seal_fn = None


def set_seal_fn(fn):
    """Inject the production seal (memory.ledger.create_event)."""
    global _seal_fn
    _seal_fn = fn


def _seal(event_type, payload):
    event = {"kind": "telemetry_ingest", "event": event_type, **payload}
    _EVENTS.append({"ts": time.time(), **event})
    if _seal_fn is not None:
        try:
            _seal_fn(event)
        except Exception:
            pass  # sealing must never break the intake


def _key(secret_value):
    return hashlib.sha3_512(secret_value.encode()).hexdigest()


def _canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def batch_fingerprint(events):
    return hashlib.sha3_512(_canon(events).encode()).hexdigest()


def sign_batch(secret_value, source_id, sequence, timestamp, events):
    """What a source computes to sign a batch."""
    body = {"source_id": source_id, "sequence": sequence,
            "timestamp": timestamp, "events": events}
    return hmac.new(_key(secret_value).encode(),
                    (_canon(body) + "|" + str(timestamp)).encode(),
                    hashlib.sha3_512).hexdigest()


def register_source(user, label=""):
    if not user:
        return {"ok": False, "error": "user required"}
    source_id = "src_" + uuid.uuid4().hex[:16]
    secret_value = secrets.token_hex(32)
    _SOURCES[source_id] = {
        "source_id": source_id, "user": user, "label": label or "",
        "secret_hash": _key(secret_value), "state": "ACTIVE",
        "registered_ts": time.time(), "last_sequence": 0,
        "accepted_batches": 0, "accepted_events": 0, "last_seen": None,
    }
    _seal("source_registered", {"source_id": source_id,
                                "label": label or ""})
    return {"ok": True, "source": {
        "source_id": source_id, "label": label or "",
        "source_secret": secret_value, "secret_shown_once": True}}


def revoke_source(source_id):
    rec = _SOURCES.get(source_id)
    if not rec:
        return {"ok": False, "error": "unknown source"}
    if rec["state"] == "REVOKED":
        return {"ok": True, "idempotent_replay": True,
                "source_id": source_id, "state": "REVOKED"}
    rec["state"] = "REVOKED"
    _seal("source_revoked", {"source_id": source_id})
    return {"ok": True, "source_id": source_id, "state": "REVOKED"}


def _reject(reason):
    _REJECTS[reason] = _REJECTS.get(reason, 0) + 1
    return {"ok": False, "accepted": False, "error": reason}


def ingest(source_id, sequence, timestamp, events, signature):
    rec = _SOURCES.get(source_id or "")
    if not rec:
        return _reject("unknown_source")
    if rec["state"] != "ACTIVE":
        return _reject("source_revoked")
    if not isinstance(events, list) or not events:
        return _reject("events_must_be_nonempty_list")
    if len(events) > MAX_EVENTS_PER_BATCH:
        return _reject("batch_too_large")
    for ev in events:
        if not isinstance(ev, dict) or not isinstance(ev.get("kind"), str):
            return _reject("event_shape_invalid")
    if not isinstance(sequence, int) or isinstance(sequence, bool):
        return _reject("sequence_must_be_integer")
    if sequence <= rec["last_sequence"]:
        return _reject("sequence_not_advancing")
    if (not isinstance(timestamp, (int, float))
            or abs(time.time() - float(timestamp)) > TIMESTAMP_WINDOW):
        return _reject("timestamp_out_of_window")
    body = {"source_id": source_id, "sequence": sequence,
            "timestamp": timestamp, "events": events}
    expected = hmac.new(rec["secret_hash"].encode(),
                        (_canon(body) + "|" + str(timestamp)).encode(),
                        hashlib.sha3_512).hexdigest()
    if not hmac.compare_digest(expected, str(signature or "")):
        return _reject("bad_signature")
    fp = batch_fingerprint(events)
    rec["last_sequence"] = sequence
    rec["accepted_batches"] += 1
    rec["accepted_events"] += len(events)
    rec["last_seen"] = time.time()
    batch = {"source_id": source_id, "sequence": sequence,
             "timestamp": timestamp, "event_count": len(events),
             "fingerprint": fp, "received_ts": time.time(),
             "events": events}
    _RING.append(batch)
    del _RING[:-RING_SIZE]
    _seal("batch_accepted", {"source_id": source_id,
                             "sequence": sequence,
                             "event_count": len(events),
                             "fingerprint": fp})
    return {"ok": True, "accepted": True, "source_id": source_id,
            "sequence": sequence, "event_count": len(events),
            "fingerprint": fp}


def recent_batches(source_id="", limit=10):
    out = [dict(b) for b in reversed(_RING)
           if not source_id or b["source_id"] == source_id]
    return {"batches": out[:max(1, min(limit, RING_SIZE))],
            "ring_size": len(_RING)}


def ingest_status():
    by_state = {}
    for rec in _SOURCES.values():
        by_state[rec["state"]] = by_state.get(rec["state"], 0) + 1
    return {
        "module": "telemetry_ingest", "owner": OWNER,
        "sources_total": len(_SOURCES), "sources_by_state": by_state,
        "connected_sources": 0,
        "accepted_batches": sum(r["accepted_batches"]
                                for r in _SOURCES.values()),
        "accepted_events": sum(r["accepted_events"]
                               for r in _SOURCES.values()),
        "rejected_by_reason": dict(_REJECTS),
        "ring_size": len(_RING),
        "state_storage": "in-memory — resets on restart; batch audit "
                         "(counts and fingerprints) is sealed to the "
                         "Golden Ledger and persists",
        "honest_scope": "this is the guarded intake door and its "
                        "logbook; no external source is connected "
                        "yet, and no historical data has been pulled "
                        "through it",
    }
