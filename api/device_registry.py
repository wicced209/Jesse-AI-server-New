"""
Trusted device registry — CRSMCPAI Alpha device-binding groundwork.

Spec source: the owner's 2026-10-15 security requirements (biometric
auth, iPhones cryptographically bound and unspoofable, no passwords,
voice+biometric-only recovery, superadmin access can never be lost)
and Jesse AI's execution-66 gap list (2026-10-30): "device binding
fingerprinting + trusted device registry — do not exist." Overnight
verification (set 10) confirmed the deployed auth checks username
membership only; nothing here weakens or replaces that lane.

Design (one construction, stated plainly):
  - Registration mints a device id and a high-entropy device secret.
    The secret is returned exactly once, for storage in the device's
    own protected store (on Jesse's iPhones: the keychain, behind
    Face ID). The raw secret never travels again and never rests on
    the server.
  - The server stores SHA3-512(secret) per device. That hash doubles
    as the proof key: the device derives the same key from its secret
    locally and answers a challenge with HMAC-SHA3-512(key, nonce);
    the server recomputes the same HMAC from the stored hash. The
    honest exposure, stated rather than hidden: a full leak of a
    device record would let someone forge that one device's proofs —
    the standard shared-secret verifier trade-off — which is why
    revocation is instant and owner-controlled, and why the stored
    hash is never sealed, listed, or returned by any endpoint.
  - Each device carries a fingerprint: SHA3-512 of its stable
    attributes (canonical JSON) as presented at registration.
  - Nonces are single-use and expire after 120 seconds.
  - Lifecycle states: ACTIVE / REVOKED. A revoked device gets no
    challenges and its proofs fail.
  - Lifecycle events (registered, proof verified, proof failed,
    revoked) are sealed through an injected seal function — in
    production, the Golden Ledger — carrying device id, label, and
    fingerprint only, never key material. Live registry state is
    in-memory and resets on restart; the audit trail persists.

What this is NOT, so nothing is oversold:
  - Not biometrics. Face ID and voice liveness live on the device,
    gating use of its secret in the keychain — client half, future
    work on the phones.
  - Not a required gate on any existing lane. The owner's standing
    law is that he must never lose superadmin access, so device proof
    stands BESIDE username auth as an additional verifiable factor
    until he directs required integration with recovery in place.
"""

import hashlib
import hmac
import json
import secrets
import time
import uuid

OWNER = "SLMK Jesse Martinez Junior"
NONCE_TTL = 120  # seconds

_DEVICES = {}     # device_id -> record (secret only as its SHA3-512)
_NONCES = {}      # nonce -> {"device_id", "ts", "used"}
_EVENTS = []      # in-memory mirror of sealed lifecycle events

_seal_fn = None


def set_seal_fn(fn):
    """Inject the production seal (memory.ledger.create_event)."""
    global _seal_fn
    _seal_fn = fn


def _seal(event_type, payload):
    event = {"kind": "device_registry", "event": event_type, **payload}
    _EVENTS.append({"ts": time.time(), **event})
    if _seal_fn is not None:
        try:
            _seal_fn(event)
        except Exception:
            pass  # sealing must never break the registry operation


def _proof_key(secret_value):
    return hashlib.sha3_512(secret_value.encode()).hexdigest()


def fingerprint_of(attributes):
    canon = json.dumps(attributes or {}, sort_keys=True)
    return hashlib.sha3_512(canon.encode()).hexdigest()


def _public(rec):
    return {k: rec[k] for k in (
        "device_id", "user", "label", "fingerprint", "state",
        "registered_ts", "last_verified_ts", "proof_count")}


def register_device(user, label="", attributes=None):
    if not user:
        return {"ok": False, "error": "user required"}
    if attributes is not None and not isinstance(attributes, dict):
        return {"ok": False, "error": "attributes must be an object"}
    device_id = "dev_" + uuid.uuid4().hex[:16]
    secret_value = secrets.token_hex(32)
    rec = {
        "device_id": device_id, "user": user, "label": label or "",
        "fingerprint": fingerprint_of(attributes),
        "secret_hash": _proof_key(secret_value),
        "state": "ACTIVE", "registered_ts": time.time(),
        "last_verified_ts": None, "proof_count": 0,
    }
    _DEVICES[device_id] = rec
    _seal("device_registered", {"device_id": device_id, "user": user,
                                "label": rec["label"],
                                "fingerprint": rec["fingerprint"]})
    out = _public(rec)
    out["device_secret"] = secret_value  # shown exactly once: here
    out["secret_shown_once"] = True
    return {"ok": True, "device": out}


def issue_challenge(device_id):
    rec = _DEVICES.get(device_id)
    if not rec:
        return {"ok": False, "error": "unknown device"}
    if rec["state"] != "ACTIVE":
        return {"ok": False,
                "error": f"device is {rec['state']} — no challenges"}
    nonce = secrets.token_hex(24)
    _NONCES[nonce] = {"device_id": device_id, "ts": time.time(),
                      "used": False}
    return {"ok": True, "device_id": device_id, "nonce": nonce,
            "ttl_seconds": NONCE_TTL}


def proof_for_secret(secret_value, nonce):
    """What a device computes: derive the proof key from its secret
    (SHA3-512 of the secret) and HMAC the nonce with it."""
    return hmac.new(_proof_key(secret_value).encode(),
                    nonce.encode(), hashlib.sha3_512).hexdigest()


def check_proof(device_id, nonce, proof, attributes=None):
    """Verify one challenge response. The nonce is consumed either
    way (single-use). If attributes are presented, fingerprint drift
    is reported alongside the result."""
    rec = _DEVICES.get(device_id)
    if not rec:
        return {"ok": False, "verified": False, "error": "unknown device"}
    if rec["state"] != "ACTIVE":
        _seal("device_proof_failed", {"device_id": device_id,
                                      "reason": f"state_{rec['state']}"})
        return {"ok": False, "verified": False,
                "error": f"device is {rec['state']}"}
    slot = _NONCES.get(nonce or "")
    if not slot or slot["device_id"] != device_id:
        return {"ok": False, "verified": False,
                "error": "unknown nonce for this device"}
    if slot["used"]:
        _seal("device_proof_failed", {"device_id": device_id,
                                      "reason": "nonce_reused"})
        return {"ok": False, "verified": False,
                "error": "nonce already used — nonces are single-use"}
    if time.time() - slot["ts"] > NONCE_TTL:
        return {"ok": False, "verified": False, "error": "nonce expired"}
    slot["used"] = True
    expected = hmac.new(rec["secret_hash"].encode(), nonce.encode(),
                        hashlib.sha3_512).hexdigest()
    if not hmac.compare_digest(expected, str(proof or "")):
        _seal("device_proof_failed", {"device_id": device_id,
                                      "reason": "bad_proof"})
        return {"ok": True, "verified": False,
                "error": "proof does not match"}
    drift = None
    if attributes is not None:
        drift = fingerprint_of(attributes) != rec["fingerprint"]
    rec["last_verified_ts"] = time.time()
    rec["proof_count"] += 1
    _seal("device_proof_verified", {"device_id": device_id,
                                    "fingerprint_drift": bool(drift)})
    return {"ok": True, "verified": True, "device_id": device_id,
            "fingerprint_drift": drift}


def revoke_device(device_id):
    rec = _DEVICES.get(device_id)
    if not rec:
        return {"ok": False, "error": "unknown device"}
    if rec["state"] == "REVOKED":
        return {"ok": True, "idempotent_replay": True,
                "device": _public(rec)}
    rec["state"] = "REVOKED"
    _seal("device_revoked", {"device_id": device_id})
    return {"ok": True, "device": _public(rec)}


def list_devices(user=""):
    out = [_public(r) for r in _DEVICES.values()
           if not user or r["user"] == user]
    return {"devices": out, "count": len(out)}


def registry_status():
    by_state = {}
    for rec in _DEVICES.values():
        by_state[rec["state"]] = by_state.get(rec["state"], 0) + 1
    return {
        "module": "device_registry", "owner": OWNER,
        "devices_total": len(_DEVICES), "devices_by_state": by_state,
        "events_recorded": len(_EVENTS),
        "state_storage": "in-memory — resets on restart; lifecycle "
                         "events are sealed to the Golden Ledger so "
                         "the audit trail persists",
        "secret_storage": "server keeps only a SHA3-512 hash of each "
                          "device secret; the secret is shown once, "
                          "at registration, and never returns",
        "biometrics": "not in this layer — Face ID / voice liveness "
                      "gate the secret on the device itself (client "
                      "half, future work)",
        "auth_integration": "additional verifiable factor beside "
                            "username auth; not a required gate on "
                            "any lane (the owner must never be "
                            "locked out)",
    }
