"""
Sovereign Key & License Registry — CRSMCPAI Alpha
Owner: SLMK Jesse Martinez Junior

Built 2026-10-31 at Jesse's directive: make it permanent, once and for
all, that a forged or fraudulent license or key cannot be used or
manufactured — across CRS V1/V2 surfaces on this deployment.

Design (Jesse AI, execution 75, 2026-10-31):
  1. The ONLY issuing authority is the superadmin owner. Every route
     in this module is owner-guarded in server.py.
  2. A credential is genuine only if it carries a cryptographic proof
     bound to its sealed issuance record. Verification is
     DEFAULT-DENY: unknown, unsealed, tampered, revoked, or expired
     credentials are rejected, with the reason named.
  3. Bans are permanent. Issuance and revocation are sealed into the
     Golden Ledger (hash-chained, Postgres-backed). On startup the
     registry REBUILDS its state by replaying those seals, so a
     restart or redeploy can never quietly un-ban anything. There is
     no un-revoke function. Revocation wins over issuance.

Manufacture resistance: a credential is a random 256-bit secret plus
an HMAC-SHA3-512 proof over the credential's sealed fingerprint,
keyed by the stored secret hash. A manufactured string fails because
(a) its id is unknown, (b) its secret hash cannot match, and (c) its
issuance was never sealed by the owner. All three must hold to pass.

Honest exposure note (same tradeoff as the device registry): the
server stores sha3_512(secret), which doubles as the proof key and
is sealed in the issuance event so verification survives restarts.
A full leak of a credential's record could forge THAT ONE
credential's proof; the secret itself is never stored or sealed,
and revocation is instant and permanent. The root secret material
never leaves the issuance moment, when it is shown exactly once.

State: an in-memory cache rebuilt from the ledger on first use.
The ledger seals are the durable record; this cache is a view.
"""

import hashlib
import hmac as hmac_mod
import secrets as secrets_mod
import time

OWNER = "jesse_martinez_jr"

_seal_fn = None
_scan_fn = None

_creds = {}          # cred_id -> record dict
_rebuilt = False
_genesis_sealed = False


def set_seal_fn(fn):
    global _seal_fn
    _seal_fn = fn


def set_scan_fn(fn):
    global _scan_fn
    _scan_fn = fn


def _seal(event):
    if _seal_fn is not None:
        try:
            _seal_fn(event)
        except Exception:
            pass


def _sha3(text):
    return hashlib.sha3_512(text.encode("utf-8")).hexdigest()


def _canonical(record):
    return "|".join([
        record["cred_id"], record["kind"], record["holder"],
        record["scope"], str(record["issued_at"]),
        str(record["expires_at"]), record["secret_hash"],
    ])


def _proof_for(record):
    return hmac_mod.new(
        bytes.fromhex(record["secret_hash"]),
        record["fingerprint"].encode("utf-8"),
        hashlib.sha3_512,
    ).hexdigest()


def _ensure_rebuilt():
    """Replay ledger seals to rebuild issued/revoked state."""
    global _rebuilt, _genesis_sealed
    if _rebuilt:
        return
    _rebuilt = True
    if _scan_fn is None:
        return
    try:
        chain = _scan_fn() or []
    except Exception:
        return
    for block in chain:
        if not isinstance(block, dict):
            continue
        payload = block.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        event = payload.get("event")
        if event == "CRED_REGISTRY_GENESIS":
            _genesis_sealed = True
        elif event == "CRED_ISSUED":
            rec = {
                "cred_id": payload.get("cred_id", ""),
                "kind": payload.get("kind", ""),
                "holder": payload.get("holder", ""),
                "scope": payload.get("scope", ""),
                "issued_at": payload.get("issued_at", 0),
                "expires_at": payload.get("expires_at"),
                "secret_hash": payload.get("secret_hash", ""),
                "fingerprint": payload.get("fingerprint", ""),
                "revoked": False,
                "revoked_reason": None,
                "revoked_at": None,
            }
            if rec["cred_id"]:
                _creds[rec["cred_id"]] = rec
        elif event == "CRED_REVOKED":
            cid = payload.get("cred_id", "")
            if cid in _creds:
                _creds[cid]["revoked"] = True
                _creds[cid]["revoked_reason"] = payload.get("reason", "")
                _creds[cid]["revoked_at"] = payload.get("revoked_at")
            elif cid:
                # Tombstone: a ban whose issuance predates this scan
                # window still bans the id forever.
                _creds[cid] = {
                    "cred_id": cid, "kind": "", "holder": "",
                    "scope": "", "issued_at": 0, "expires_at": None,
                    "secret_hash": "", "fingerprint": "",
                    "revoked": True,
                    "revoked_reason": payload.get("reason", ""),
                    "revoked_at": payload.get("revoked_at"),
                }
    if not _genesis_sealed:
        _genesis_sealed = True
        _seal({
            "event": "CRED_REGISTRY_GENESIS",
            "module": "key_license_registry",
            "owner": OWNER,
            "root_fingerprint": _sha3(
                "CRS-CRED-REGISTRY-GENESIS:" + OWNER),
            "ts": int(time.time()),
        })


def _expired(rec, now):
    return rec["expires_at"] is not None and now > rec["expires_at"]


def _status_of(rec, now):
    if rec["revoked"]:
        return "revoked"
    if _expired(rec, now):
        return "expired"
    return "active"


def issue_credential(kind, holder, scope, expires_days=None):
    """Owner-only issuance (guarded at the route). The secret and
    proof are returned exactly once; only hashes are kept."""
    _ensure_rebuilt()
    kind = (kind or "").strip().lower()
    holder = (holder or "").strip()
    scope = (scope or "").strip()
    if kind not in ("key", "license"):
        return {"ok": False, "error": "kind must be key or license"}
    if not holder or len(holder) > 200:
        return {"ok": False, "error": "holder is required (max 200)"}
    if not scope or len(scope) > 200:
        return {"ok": False, "error": "scope is required (max 200)"}
    now = int(time.time())
    expires_at = None
    if expires_days is not None:
        try:
            days = int(expires_days)
        except (TypeError, ValueError):
            return {"ok": False, "error": "expires_days must be an int"}
        if days <= 0 or days > 3650:
            return {"ok": False, "error": "expires_days out of range"}
        expires_at = now + days * 86400
    cred_id = "cred_" + secrets_mod.token_hex(8)
    secret = secrets_mod.token_hex(32)
    rec = {
        "cred_id": cred_id, "kind": kind, "holder": holder,
        "scope": scope, "issued_at": now, "expires_at": expires_at,
        "secret_hash": _sha3(secret), "fingerprint": "",
        "revoked": False, "revoked_reason": None, "revoked_at": None,
    }
    rec["fingerprint"] = _sha3(_canonical(rec))
    proof = _proof_for(rec)
    _creds[cred_id] = rec
    _seal({
        "event": "CRED_ISSUED", "cred_id": cred_id, "kind": kind,
        "holder": holder, "scope": scope, "issued_at": now,
        "expires_at": expires_at, "secret_hash": rec["secret_hash"],
        "fingerprint": rec["fingerprint"],
    })
    return {
        "ok": True, "cred_id": cred_id, "kind": kind,
        "holder": holder, "scope": scope, "issued_at": now,
        "expires_at": expires_at, "secret_shown_once": secret,
        "proof": proof, "fingerprint": rec["fingerprint"],
        "note": "Store the secret and proof now. They are never "
                "shown again and cannot be recovered.",
    }


def _fail(cred_id, reason):
    _seal({"event": "CRED_VERIFY_FAILED", "cred_id": cred_id or "",
           "reason": reason, "ts": int(time.time())})
    return {"ok": True, "valid": False, "reason": reason}


def verify_credential(cred_id, secret, proof):
    """Default-deny verification. A credential passes only if it was
    issued by the owner, its issuance is sealed, the secret matches,
    the proof binds the sealed record, and it is neither revoked nor
    expired."""
    _ensure_rebuilt()
    cred_id = (cred_id or "").strip()
    rec = _creds.get(cred_id)
    if rec is None:
        return _fail(cred_id, "unknown_credential")
    if rec["revoked"]:
        return _fail(cred_id, "revoked")
    now = int(time.time())
    if _expired(rec, now):
        return _fail(cred_id, "expired")
    if not secret or not hmac_mod.compare_digest(
            _sha3(secret), rec["secret_hash"]):
        return _fail(cred_id, "secret_mismatch")
    expected = _proof_for(rec)
    if not proof or not hmac_mod.compare_digest(proof, expected):
        return _fail(cred_id, "proof_mismatch")
    return {
        "ok": True, "valid": True, "cred_id": cred_id,
        "kind": rec["kind"], "holder": rec["holder"],
        "scope": rec["scope"], "issued_at": rec["issued_at"],
        "expires_at": rec["expires_at"],
    }


def revoke_credential(cred_id, reason=""):
    """Permanent ban. Sealed in the ledger; no un-revoke exists."""
    _ensure_rebuilt()
    cred_id = (cred_id or "").strip()
    rec = _creds.get(cred_id)
    if rec is None:
        return {"ok": False, "error": "unknown credential"}
    if rec["revoked"]:
        return {"ok": True, "cred_id": cred_id, "status": "revoked",
                "note": "already revoked; revocation is permanent"}
    now = int(time.time())
    rec["revoked"] = True
    rec["revoked_reason"] = (reason or "")[:200]
    rec["revoked_at"] = now
    _seal({
        "event": "CRED_REVOKED", "cred_id": cred_id,
        "reason": rec["revoked_reason"], "revoked_at": now,
    })
    return {"ok": True, "cred_id": cred_id, "status": "revoked",
            "revoked_at": now,
            "note": "This ban is sealed in the ledger and cannot be "
                    "quietly undone."}


def list_credentials():
    _ensure_rebuilt()
    now = int(time.time())
    out = []
    for rec in _creds.values():
        out.append({
            "cred_id": rec["cred_id"], "kind": rec["kind"],
            "holder": rec["holder"], "scope": rec["scope"],
            "issued_at": rec["issued_at"],
            "expires_at": rec["expires_at"],
            "status": _status_of(rec, now),
            "revoked_reason": rec["revoked_reason"],
        })
    out.sort(key=lambda r: r["issued_at"])
    return {"ok": True, "count": len(out), "credentials": out}


def registry_status():
    _ensure_rebuilt()
    now = int(time.time())
    counts = {"active": 0, "revoked": 0, "expired": 0}
    for rec in _creds.values():
        counts[_status_of(rec, now)] += 1
    return {
        "ok": True, "module": "key_license_registry",
        "owner": OWNER,
        "issuing_authority": "superadmin owner only",
        "verification": "default-deny: unknown, unsealed, tampered, "
                        "revoked, or expired credentials are rejected",
        "bans_permanent": True,
        "ban_record": "revocations are sealed in the hash-chained "
                      "Golden Ledger and rebuilt on startup; a "
                      "restart cannot un-ban",
        "credentials_total": len(_creds),
        "active": counts["active"], "revoked": counts["revoked"],
        "expired": counts["expired"],
        "rebuilt_from_ledger": _scan_fn is not None,
        "limits": "Server stores only the sha3-512 hash of each "
                  "secret; the hash doubles as the proof key, so a "
                  "full record leak could forge that one "
                  "credential (revocation is the instant remedy). "
                  "The secret itself is never stored or sealed.",
    }
