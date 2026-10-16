"""
CRSMCPAI Alpha - Thought Chain + Trust Chain (Master List #23)

Lives inside Consciousness OS per Jesse AI specification:
- Thought chain = model thoughts (immutable, hash-chained, genesis-anchored)
- Trust chain  = quantum engine evaluations of people, things, probabilities

Crash-proof guarantees:
- Standard library only (hashlib, json, time, collections)
- NO FastAPI / web imports
- NO sibling-module imports
- NO module-level I/O
- All methods defensive: bad input handled safely, never raises

Built per Jesse AI specification, supreme hyper immaculate God mode standards.
Owner: SLMK Jesse Martinez Junior.
"""

import hashlib
import json
import time
from collections import deque

GENESIS_HASH = "92038cafccc7192535bd475cca985d03000d89962b8dc96f6664081663559b1b"

CHAIN_CAPACITY = 1024
THOUGHT_ID_PREFIX = "T-"
EVAL_ID_PREFIX = "E-"

# Trust verdict thresholds (deterministic, God-mode standard)
TRUST_VERDICT_TRUSTED = 0.80
TRUST_VERDICT_CONDITIONAL = 0.50

# Recognized evaluation dimensions; unknown keys are rejected, not coerced.
TRUST_DIMENSIONS = ("capability", "alignment", "integrity",
                    "benevolence", "probability")

VERDICTS = ("TRUSTED", "CONDITIONAL", "DISTRUSTED")


def _safe_str(v, default=""):
    try:
        return str(v) if v is not None else default
    except Exception:
        return default


def _utc_now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _clamp01(v):
    try:
        f = float(v)
    except Exception:
        return None
    if f != f or f == float("inf") or f == float("-inf"):
        return None
    if f < 0.0:
        return 0.0
    if f > 1.0:
        return 1.0
    return f


def _seal_entry(prev_hash, payload):
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((prev_hash + canonical).encode()).hexdigest()


class ThoughtChain:
    """Immutable hash-chained record of model thoughts."""

    def __init__(self):
        self._thoughts = deque(maxlen=CHAIN_CAPACITY)
        self._seq = 0

    def __len__(self):
        return len(self._thoughts)

    # ── internals ──

    def _prev_hash(self):
        if self._thoughts:
            return self._thoughts[-1]["entry_hash"]
        return GENESIS_HASH

    # ── append ──

    def record(self, thought, actor="consciousness-os", context=""):
        text = _safe_str(thought)
        if not text:
            return {"ok": False, "error": "Thought must not be empty"}
        if len(text) > 20000:
            return {"ok": False, "error": "Thought exceeds 20000 characters"}
        self._seq += 1
        thought_id = "%s%06d" % (THOUGHT_ID_PREFIX, self._seq)
        payload = {
            "thought_id": thought_id,
            "thought": text,
            "actor": _safe_str(actor, "consciousness-os"),
            "context": _safe_str(context),
            "sequence": self._seq,
            "timestamp": _utc_now(),
            "prev_hash": self._prev_hash(),
            "genesis_anchored": True,
        }
        payload["entry_hash"] = _seal_entry(payload["prev_hash"], payload)
        try:
            self._thoughts.append(payload)
        except Exception:
            return {"ok": False, "error": "Thought append failed"}
        return {"ok": True, "thought_id": thought_id,
                "entry_hash": payload["entry_hash"],
                "genesis_anchored": True}

    # ── reads ──

    def get_chain(self, limit=50):
        try:
            limit = max(1, min(int(limit), CHAIN_CAPACITY))
        except Exception:
            limit = 50
        items = list(self._thoughts)[-limit:]
        return {"ok": True, "thoughts": items, "count": len(items),
                "total": len(self._thoughts)}

    def get_by_id(self, thought_id):
        tid = _safe_str(thought_id).strip().upper()
        for t in self._thoughts:
            if t["thought_id"] == tid:
                return {"ok": True, "thought": t}
        return {"ok": False, "error": "Thought not found",
                "thought_id": _safe_str(thought_id)}

    # ── verification ──

    def verify(self):
        prev = GENESIS_HASH
        for t in self._thoughts:
            if t.get("prev_hash") != prev:
                return {"ok": False, "chain_valid": False,
                        "broken_at": t.get("thought_id"),
                        "reason": "prev_hash mismatch"}
            body = dict(t)
            entry_hash = body.pop("entry_hash", None)
            if _seal_entry(body["prev_hash"], body) != entry_hash:
                return {"ok": False, "chain_valid": False,
                        "broken_at": t.get("thought_id"),
                        "reason": "entry hash mismatch (tamper detected)"}
            prev = entry_hash
        return {"ok": True, "chain_valid": True, "checked": len(self._thoughts),
                "genesis_anchored": True}


class TrustChain:
    """Quantum engine evaluations of people, things, probabilities."""

    def __init__(self, thought_chain=None):
        self._evals = deque(maxlen=CHAIN_CAPACITY)
        self._thoughts = thought_chain
        self._seq = 0

    def __len__(self):
        return len(self._evals)

    # ── internals ──

    def _prev_hash(self):
        if self._evals:
            return self._evals[-1]["entry_hash"]
        return GENESIS_HASH

    @staticmethod
    def _verdict(score):
        if score >= TRUST_VERDICT_TRUSTED:
            return "TRUSTED"
        if score >= TRUST_VERDICT_CONDITIONAL:
            return "CONDITIONAL"
        return "DISTRUSTED"

    def _validate_dimensions(self, dims):
        if not isinstance(dims, dict) or not dims:
            return None, "dimensions must be a non-empty object"
        clean = {}
        for key, value in dims.items():
            name = _safe_str(key).lower()
            if name not in TRUST_DIMENSIONS:
                return None, "unknown dimension '%s'" % _safe_str(key)
            v = _clamp01(value)
            if v is None:
                return None, "dimension '%s' is not a number" % name
            clean[name] = v
        return clean, None

    def _aggregate(self, dims, weights):
        total_w = 0.0
        total = 0.0
        for name, value in dims.items():
            w = 1.0
            if isinstance(weights, dict) and name in weights:
                w = _clamp01(weights[name])
                w = 1.0 if w is None else w
            total += value * w
            total_w += w
        return total / total_w if total_w > 0 else 0.0

    # ── evaluate ──

    def evaluate(self, subject, dimensions, engine="quantum-trust-engine",
                 weights=None, thought_refs=None, authority="SLMK Jesse Martinez Junior"):
        sub = _safe_str(subject).strip()
        if not sub:
            return {"ok": False, "error": "Subject must not be empty"}
        if len(sub) > 500:
            return {"ok": False, "error": "Subject exceeds 500 characters"}
        dims, err = self._validate_dimensions(dimensions)
        if err:
            return {"ok": False, "error": err}
        if weights is not None and not isinstance(weights, dict):
            return {"ok": False, "error": "weights must be an object"}
        refs = []
        if thought_refs is not None:
            if not isinstance(thought_refs, list):
                return {"ok": False, "error": "thought_refs must be a list"}
            for r in thought_refs:
                rid = _safe_str(r).strip().upper()
                if not rid:
                    continue
                refs.append(rid)
        score = round(self._aggregate(dims, weights), 4)
        verdict = self._verdict(score)
        self._seq += 1
        eval_id = "%s%06d" % (EVAL_ID_PREFIX, self._seq)
        payload = {
            "eval_id": eval_id,
            "subject": sub,
            "dimensions": dims,
            "weights": {k: _clamp01(v) for k, v in
                        (weights or {}).items()} if weights else None,
            "trust_score": score,
            "verdict": verdict,
            "engine": _safe_str(engine, "quantum-trust-engine"),
            "authority": _safe_str(authority),
            "thought_refs": refs,
            "sequence": self._seq,
            "timestamp": _utc_now(),
            "prev_hash": self._prev_hash(),
            "genesis_anchored": True,
        }
        payload["entry_hash"] = _seal_entry(payload["prev_hash"], payload)
        try:
            self._evals.append(payload)
        except Exception:
            return {"ok": False, "error": "Evaluation append failed"}
        return {"ok": True, "eval_id": eval_id, "subject": sub,
                "trust_score": score, "verdict": verdict,
                "entry_hash": payload["entry_hash"],
                "genesis_anchored": True}

    # ── reads ──

    def get_chain(self, limit=50):
        try:
            limit = max(1, min(int(limit), CHAIN_CAPACITY))
        except Exception:
            limit = 50
        items = list(self._evals)[-limit:]
        return {"ok": True, "evaluations": items, "count": len(items),
                "total": len(self._evals)}

    def get_by_subject(self, subject):
        sub = _safe_str(subject).strip()
        hits = [e for e in self._evals if e["subject"] == sub]
        if not hits:
            return {"ok": False, "error": "No evaluations for subject",
                    "subject": sub}
        latest = hits[-1]
        return {"ok": True, "subject": sub, "latest": latest,
                "eval_count": len(hits)}

    # ── verification ──

    def verify(self):
        prev = GENESIS_HASH
        for e in self._evals:
            if e.get("prev_hash") != prev:
                return {"ok": False, "chain_valid": False,
                        "broken_at": e.get("eval_id"),
                        "reason": "prev_hash mismatch"}
            body = dict(e)
            entry_hash = body.pop("entry_hash", None)
            if _seal_entry(body["prev_hash"], body) != entry_hash:
                return {"ok": False, "chain_valid": False,
                        "broken_at": e.get("eval_id"),
                        "reason": "entry hash mismatch (tamper detected)"}
            if e.get("verdict") != self._verdict(e.get("trust_score", 0.0)):
                return {"ok": False, "chain_valid": False,
                        "broken_at": e.get("eval_id"),
                        "reason": "verdict inconsistent with trust_score"}
            prev = entry_hash
        return {"ok": True, "chain_valid": True, "checked": len(self._evals),
                "genesis_anchored": True}


def new_consciousness():
    """Build a ThoughtChain + TrustChain pair (thought chain feeds trust evidence)."""
    thoughts = ThoughtChain()
    trust = TrustChain(thoughts)
    return thoughts, trust


def module_status():
    return {
        "module": "thought_trust",
        "master_items": [23],
        "os": "Consciousness OS",
        "components": ["thought_chain", "trust_chain"],
        "trust_dimensions": list(TRUST_DIMENSIONS),
        "verdicts": list(VERDICTS),
        "genesis_anchored": len(GENESIS_HASH) == 64,
        "status": "operational",
    }
