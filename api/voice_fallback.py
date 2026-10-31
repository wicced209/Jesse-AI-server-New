"""
Voice fallback speaker registry — CRSMCPAI Alpha groundwork.

Spec source: the owner's 2026-10-15 security requirements (voice ID
with liveness as an authentication factor, voice+biometric-only
fallback recovery, no passwords) and Jesse AI's execution-66 gap
list (2026-10-30): "voice fallback embeddings for speaker
recognition — absent."

What this module is, exactly:
  - A registry of speaker embeddings (fixed-dimension float vectors)
    with cosine-similarity matching: enroll samples for a speaker,
    verify a new sample against them, threshold decides the match.
  - Matching is proven here with SYNTHETIC vectors. Real enrollment
    needs embeddings extracted from the owner's actual voice by a
    real voice model — the whisper lane is a stub today — so real
    enrollment is a sitting with Jesse once extraction exists.
    Nothing here claims to identify anyone yet.
  - It extracts nothing from audio. It holds no audio. Embeddings
    live in memory only (biometric-adjacent data is never sealed and
    never written to disk by this module); verification ATTEMPTS are
    sealed as counts and outcomes only, never vectors.
  - Liveness is not in this layer; a recording could in principle
    produce a matching embedding. Voice match here is one factor
    beside the device registry and username auth, never a sole gate —
    the owner must never be locked out by his own fallback.
"""

import hashlib
import json
import math
import time
import uuid

OWNER = "SLMK Jesse Martinez Junior"
MIN_DIM = 8
MAX_DIM = 1024
DEFAULT_THRESHOLD = 0.85

_SPEAKERS = {}    # speaker_id -> record
_DIM = None       # registry-wide dimension, set by first enrollment
_EVENTS = []      # in-memory mirror of sealed events

_seal_fn = None


def set_seal_fn(fn):
    """Inject the production seal (memory.ledger.create_event)."""
    global _seal_fn
    _seal_fn = fn


def _seal(event_type, payload):
    event = {"kind": "voice_fallback", "event": event_type, **payload}
    _EVENTS.append({"ts": time.time(), **event})
    if _seal_fn is not None:
        try:
            _seal_fn(event)
        except Exception:
            pass


def _validate_vector(vec):
    if not isinstance(vec, list) or not vec:
        return "embedding must be a non-empty list of numbers"
    if not (MIN_DIM <= len(vec) <= MAX_DIM):
        return f"embedding dimension must be {MIN_DIM}..{MAX_DIM}"
    for x in vec:
        if (not isinstance(x, (int, float)) or isinstance(x, bool)
                or not math.isfinite(x)):
            return "embedding values must be finite numbers"
    if _DIM is not None and len(vec) != _DIM:
        return f"embedding dimension is locked to {_DIM} in this registry"
    norm = math.sqrt(sum(float(x) * float(x) for x in vec))
    if norm == 0.0:
        return "embedding must not be the zero vector"
    return None


def _normalized(vec):
    norm = math.sqrt(sum(float(x) * float(x) for x in vec))
    return [float(x) / norm for x in vec]


def _cosine(a, b):
    return sum(x * y for x, y in zip(a, b))


def _vector_fingerprint(vec):
    canon = json.dumps([round(float(x), 6) for x in vec])
    return hashlib.sha3_512(canon.encode()).hexdigest()[:16]


def enroll_speaker(user, label, embedding):
    global _DIM
    if not user:
        return {"ok": False, "error": "user required"}
    err = _validate_vector(embedding)
    if err:
        return {"ok": False, "error": err}
    if _DIM is None:
        _DIM = len(embedding)
    speaker_id = "spk_" + uuid.uuid4().hex[:16]
    unit = _normalized(embedding)
    _SPEAKERS[speaker_id] = {
        "speaker_id": speaker_id, "user": user,
        "label": label or "", "state": "ACTIVE",
        "enrolled_ts": time.time(), "samples": [unit],
        "sample_fingerprints": [_vector_fingerprint(unit)],
        "verify_attempts": 0, "verify_matches": 0,
    }
    _seal("speaker_enrolled", {"speaker_id": speaker_id,
                               "dimension": _DIM})
    return {"ok": True, "speaker_id": speaker_id, "dimension": _DIM,
            "samples": 1}


def add_sample(speaker_id, embedding):
    rec = _SPEAKERS.get(speaker_id)
    if not rec:
        return {"ok": False, "error": "unknown speaker"}
    if rec["state"] != "ACTIVE":
        return {"ok": False, "error": "speaker is not active"}
    err = _validate_vector(embedding)
    if err:
        return {"ok": False, "error": err}
    unit = _normalized(embedding)
    rec["samples"].append(unit)
    rec["sample_fingerprints"].append(_vector_fingerprint(unit))
    _seal("speaker_sample_added", {"speaker_id": speaker_id,
                                   "samples": len(rec["samples"])})
    return {"ok": True, "speaker_id": speaker_id,
            "samples": len(rec["samples"])}


def verify_speaker(speaker_id, embedding, threshold=DEFAULT_THRESHOLD):
    rec = _SPEAKERS.get(speaker_id)
    if not rec:
        return {"ok": False, "matched": False,
                "error": "unknown speaker"}
    if rec["state"] != "ACTIVE":
        return {"ok": False, "matched": False,
                "error": "speaker is not active"}
    err = _validate_vector(embedding)
    if err:
        return {"ok": False, "matched": False, "error": err}
    if (not isinstance(threshold, (int, float))
            or not (0.0 < float(threshold) <= 1.0)):
        return {"ok": False, "matched": False,
                "error": "threshold must be in (0, 1]"}
    unit = _normalized(embedding)
    best = max(_cosine(unit, s) for s in rec["samples"])
    matched = best >= float(threshold)
    rec["verify_attempts"] += 1
    rec["verify_matches"] += int(matched)
    _seal("speaker_verify_attempt",
          {"speaker_id": speaker_id, "matched": matched,
           "score_bucket": round(best, 1)})
    return {"ok": True, "speaker_id": speaker_id, "matched": matched,
            "best_score": round(best, 6),
            "threshold": float(threshold)}


def revoke_speaker(speaker_id):
    rec = _SPEAKERS.get(speaker_id)
    if not rec:
        return {"ok": False, "error": "unknown speaker"}
    if rec["state"] == "REVOKED":
        return {"ok": True, "idempotent_replay": True,
                "speaker_id": speaker_id, "state": "REVOKED"}
    rec["state"] = "REVOKED"
    _seal("speaker_revoked", {"speaker_id": speaker_id})
    return {"ok": True, "speaker_id": speaker_id, "state": "REVOKED"}


def list_speakers():
    out = []
    for rec in _SPEAKERS.values():
        out.append({k: rec[k] for k in (
            "speaker_id", "user", "label", "state", "enrolled_ts",
            "verify_attempts", "verify_matches")} |
            {"samples": len(rec["samples"]),
             "sample_fingerprints": list(rec["sample_fingerprints"])})
    return {"speakers": out, "count": len(out), "dimension": _DIM}


def voice_status():
    return {
        "module": "voice_fallback", "owner": OWNER,
        "speakers": len(_SPEAKERS), "dimension": _DIM,
        "default_threshold": DEFAULT_THRESHOLD,
        "embeddings_storage": "in-memory only — vectors are never "
                              "sealed and never written to disk",
        "audio": "none held; this module does not extract "
                 "embeddings from audio",
        "verification_proven_with": "synthetic vectors only — real "
                                    "voice enrollment waits on a "
                                    "working voice model and a "
                                    "sitting with the owner",
        "liveness": "not in this layer — voice match is one factor "
                    "beside device proof and username auth, never "
                    "a sole gate",
    }
