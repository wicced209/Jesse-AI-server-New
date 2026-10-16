"""
Jesse AI / CRSMCPAI Alpha — Sovereign Model Runtime
Owner: SLMK Jesse Martinez Junior

Item #49 (100% Sovereign Model — replace Gemini relay).

This module establishes the sovereign-model runtime layer: model identity,
CRSMCPAI mediation (every generation is mediated and sealed — no direct
bypass), local-first backend arbitration (sovereign-local inference first,
external relay only as fallback), a sovereign-weights manifest, and
sovereignty-status reporting.

Scope note (honest record): a fully sovereign trained model (independent
weight files running 100% on Jesse's infrastructure with zero external
relay) is the remaining step of #49. This runtime builds the executable
foundation: mediation, arbitration, registration, and reporting — so that
when sovereign weights exist they register here and arbitration becomes
100% local with zero code changes elsewhere.
"""

import os
import json
import time
import hashlib
import urllib.request
import urllib.error

GENESIS_HASH = "92038cafccc7192535bd475cca985d03000d89962b8dc96f6664081663559b1b"
MODULE_NAME = "sovereign_model"
SOVEREIGN_OWNER = "SLMK Jesse Martinez Junior"

MODEL_IDENTITY = {
    "model_id": "JESSE-AI-SOVEREIGN-1",
    "lineage": "CRSMCPAI Alpha V2 — 100% sovereign line",
    "owner": SOVEREIGN_OWNER,
    "genesis_hash": GENESIS_HASH,
    "purpose": "Replace external relays (Gemini/Groq) with sovereign-local inference.",
}

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
LOCAL_MODEL = os.environ.get("LOCAL_MODEL", "llama3")

SOVEREIGN_LOCAL = "sovereign-local"
RELAY_EXTERNAL = "relay-external"

# Backend registry: sovereignty class, not marketing.
_DEFAULT_BACKENDS = [
    {
        "backend_id": "ollama-local",
        "class": SOVEREIGN_LOCAL,
        "description": "Local Ollama inference on Jesse's infrastructure (no external relay).",
        "endpoint": OLLAMA_URL,
        "model": LOCAL_MODEL,
        "enabled": True,
    },
    {
        "backend_id": "gemini-relay",
        "class": RELAY_EXTERNAL,
        "description": "External Gemini relay — dependency to be replaced per #49.",
        "enabled": True,
    },
    {
        "backend_id": "groq-relay",
        "class": RELAY_EXTERNAL,
        "description": "External Groq relay — dependency to be replaced per #49.",
        "enabled": True,
    },
]


def _seal(payload: dict) -> str:
    """Deterministic genesis-anchored seal for mediation records."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(
        (GENESIS_HASH + canonical).encode("utf-8")
    ).hexdigest()


def module_status() -> dict:
    return {
        "module": MODULE_NAME,
        "owner": SOVEREIGN_OWNER,
        "model_identity": MODEL_IDENTITY,
        "status": "LIVE",
        "sovereign_weights_registered": False,
        "note": (
            "Sovereign runtime foundation live: mediation, local-first "
            "arbitration, weights manifest, sovereignty reporting. "
            "Fully sovereign trained weights remain the final step of #49."
        ),
    }


class SovereignModelRuntime:
    """
    CRSMCPAI-mediated sovereign model runtime.

    Every generation is CRSMCPAI-mediated: a mediation record (request id,
    prompt hash, genesis anchor, seal) is created BEFORE any backend is
    called. Sovereign-local backends are tried first; external relays are
    used only as fallback and are flagged as non-sovereign in the output.
    """

    def __init__(self):
        self._backends = [dict(b) for b in _DEFAULT_BACKENDS]
        self._weights_manifest = []          # registered sovereign weight files
        self._mediation_log = []             # append-only, cap 1024
        self._seq = 0

    # ---- backend registry -------------------------------------------
    def list_backends(self) -> list:
        return [dict(b) for b in self._backends]

    def set_backend_enabled(self, backend_id: str, enabled: bool) -> dict:
        for b in self._backends:
            if b["backend_id"] == backend_id:
                b["enabled"] = bool(enabled)
                return {"ok": True, "backend_id": backend_id,
                        "enabled": b["enabled"]}
        return {"ok": False, "error": f"unknown backend: {backend_id}"}

    # ---- sovereign weights manifest ---------------------------------
    def register_weights(self, path: str, sha256: str,
                         provenance: str = "") -> dict:
        """Register a sovereign weight file (future final step of #49)."""
        if not path or not isinstance(path, str):
            return {"ok": False, "error": "path required"}
        if not sha256 or not isinstance(sha256, str):
            return {"ok": False, "error": "sha256 required"}
        entry = {
            "path": path,
            "sha256": sha256.lower(),
            "provenance": provenance or "",
            "registered_at": time.time(),
            "genesis_anchor": GENESIS_HASH,
            "seal": _seal({"path": path, "sha256": sha256.lower()}),
        }
        self._weights_manifest.append(entry)
        return {"ok": True, "entry": entry,
                "weights_count": len(self._weights_manifest)}

    def weights_manifest(self) -> list:
        return [dict(w) for w in self._weights_manifest]

    # ---- CRSMCPAI mediation (no bypass) ------------------------------
    def mediate(self, prompt: str, user: str = "jesse_martinez_jr") -> dict:
        if not prompt or not isinstance(prompt, str):
            return {"ok": False, "error": "prompt required"}
        self._seq += 1
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        record = {
            "ok": True,
            "request_id": f"SM-{self._seq:06d}",
            "user": user,
            "prompt_hash": prompt_hash,
            "genesis_anchor": GENESIS_HASH,
            "mediated_at": time.time(),
            "mediator": "CRSMCPAI Alpha",
            "owner": SOVEREIGN_OWNER,
        }
        record["seal"] = _seal({k: record[k] for k in
                                ("request_id", "user", "prompt_hash",
                                 "genesis_anchor")})
        self._mediation_log.append(record)
        if len(self._mediation_log) > 1024:
            self._mediation_log = self._mediation_log[-1024:]
        return dict(record)

    def mediation_log(self, limit: int = 50) -> list:
        try:
            limit = max(1, min(int(limit), 200))
        except (TypeError, ValueError):
            limit = 50
        return [dict(r) for r in self._mediation_log[-limit:]]

    # ---- arbitration + generation ------------------------------------
    def _try_local(self, prompt: str, mediation: dict,
                   timeout: int = 60) -> dict | None:
        backend = next((b for b in self._backends
                        if b["backend_id"] == "ollama-local"
                        and b["enabled"]), None)
        if backend is None:
            return None
        payload = json.dumps({
            "model": backend["model"],
            "prompt": prompt,
            "stream": False,
        }).encode("utf-8")
        try:
            req = urllib.request.Request(
                backend["endpoint"], data=payload,
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = json.loads(r.read().decode("utf-8"))
            return {
                "ok": True,
                "output": body.get("response", ""),
                "backend_id": backend["backend_id"],
                "class": SOVEREIGN_LOCAL,
                "sovereign": True,
                "request_id": mediation["request_id"],
                "mediation_seal": mediation["seal"],
            }
        except Exception as e:  # local unavailable -> relay fallback path
            return {"ok": False, "error": f"sovereign-local unavailable: {e}"}

    def generate(self, prompt: str, user: str = "jesse_martinez_jr",
                 prefer_sovereign: bool = True,
                 allow_relay_fallback: bool = True) -> dict:
        """
        CRSMCPAI-mediated generation with local-first arbitration.
        Relay fallback is flagged non-sovereign and routed to the existing
        /command relay (models.ollama_runtime handles external relays).
        """
        mediation = self.mediate(prompt, user)
        if not mediation.get("ok"):
            return mediation

        result = None
        if prefer_sovereign:
            result = self._try_local(prompt, mediation)

        if result and result.get("ok"):
            result["owner"] = SOVEREIGN_OWNER
            return result

        local_error = (result or {}).get("error")
        if not allow_relay_fallback:
            return {"ok": False, "error": local_error or
                    "sovereign-local unavailable, relay fallback disabled",
                    "request_id": mediation["request_id"],
                    "mediation_seal": mediation["seal"],
                    "sovereign": True}

        # Structured relay-fallback record (non-sovereign, audited).
        return {
            "ok": True,
            "output": None,
            "sovereign": False,
            "class": RELAY_EXTERNAL,
            "request_id": mediation["request_id"],
            "mediation_seal": mediation["seal"],
            "relay_route": "/command",
            "relay_reason": local_error or
            "sovereign-local skipped; relay arbitration",
            "note": ("Route via POST /command (existing relay chain) until "
                     "sovereign weights are registered. "
                     "Sovereignty unaffected: mediation seal preserved."),
            "owner": SOVEREIGN_OWNER,
        }

    # ---- sovereignty reporting ---------------------------------------
    def sovereignty_status(self) -> dict:
        backends = self.list_backends()
        sovereign_backends = [b for b in backends
                              if b["class"] == SOVEREIGN_LOCAL and b["enabled"]]
        total = len(backends) or 1
        pct = round(100.0 * len(sovereign_backends) / total, 1)
        weights = len(self._weights_manifest)
        if pct >= 100 and weights > 0:
            level = "SOVEREIGN (100%)"
        elif pct >= 100:
            level = "SOVEREIGN RUNTIME — weights pending (final step)"
        elif pct >= 50:
            level = "PARTIAL"
        else:
            level = "RELAY-DEPENDENT"
        return {
            "model_id": MODEL_IDENTITY["model_id"],
            "owner": SOVEREIGN_OWNER,
            "sovereign_backends": len(sovereign_backends),
            "total_backends": len(backends),
            "sovereignty_percent": pct,
            "level": level,
            "weights_registered": weights,
            "mediations_total": self._seq,
            "backends": backends,
        }


def new_runtime() -> SovereignModelRuntime:
    return SovereignModelRuntime()
