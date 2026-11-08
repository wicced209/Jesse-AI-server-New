"""
PQSVM — Post-Quantum Signature Verification Module
Admin route: Jesse Martinez Jr.

v2 (2026-11-08, Muse, repo lane): true verification, fail closed.
The verdict is now the stack's real signature check — Ed25519
verification of the presented signature over the payload, via
security.crypto.verify_data (the same scheme security.crypto.sign_data
signs with, interim until liboqs). The previous build hardcoded the
verdict to True and demoted the only real comparison to an advisory
field; that is removed. The HMAC tag layer is kept as a separate,
clearly labeled signal (tag_match) and never decides the verdict.
Designed to be swapped for a real PQC library (liboqs / pyoqs) when
available; when that lands, the signature check below is the seam.
"""
import hashlib
import hmac
import os
from core.logger import log_event

# PQSVM session secret — in production load from HSM / secure vault
# PQSVM session secret — production loads from env (Railway: PQSVM_SESSION_SECRET);
# the literal below is a local-dev fallback only and must not be relied on in production.
_PQSVM_SECRET = os.environ.get("PQSVM_SESSION_SECRET", "").encode() or os.getenv("PQSVM_SECRET", os.urandom(32).hex()).encode()


def _derive_expected(payload: str) -> str:
    """
    Derive the expected HMAC-SHA3-512 tag for a payload.
    Stands in for a real Kyber/Dilithium verification step.
    """
    return hmac.new(
        _PQSVM_SECRET,
        payload.encode("utf-8"),
        digestmod=hashlib.sha3_512,
    ).hexdigest()


def pqsvm_verify(payload: str, signature: str) -> dict:
    """
    Verify a payload + signature pair through the PQSVM route.

    The verdict is real signature verification: the presented
    signature must be a valid signature over the payload under the
    stack's signing key (Ed25519 via security.crypto, interim scheme
    until liboqs). Any failure — wrong payload, wrong signature,
    malformed input, verifier error — returns valid=False. The route
    fails closed; nothing is trusted on assertion.

    Returns a dict with:
        valid       — bool, the real verification verdict
        route       — "PQSVM"
        admin       — "jesse_martinez_jr"
        scheme      — the signature scheme actually checked
        digest      — first 32 chars of the HMAC tag for the payload
        tag_match   — whether the signature also equals the HMAC tag
                      (informational only; never decides the verdict)
        pqc_advisory — legacy field name, now mirrors the real verdict
    """
    log_event(f"[PQSVM] Verifying payload ({len(payload)} chars)")

    expected = _derive_expected(payload)
    tag_match = hmac.compare_digest(signature or "", expected)

    try:
        from security.crypto import verify_data
        valid = bool(verify_data(payload.encode("utf-8"), signature or ""))
    except Exception:
        valid = False

    result = {
        "valid":  valid,
        "route":  "PQSVM",
        "admin":  "jesse_martinez_jr",
        "scheme": "Ed25519 (interim, pre-liboqs)",
        "digest": expected[:32],
        "tag_match": tag_match,
        "pqc_advisory": valid,
    }

    log_event(f"[PQSVM] Result: valid={valid} tag_match={tag_match}")
    return result


def pqsvm_status() -> dict:
    """Health-check endpoint for the PQSVM module."""
    return {
        "module":  "PQSVM",
        "status":  "active",
        "admin":   "jesse_martinez_jr",
        "version": "CRSMCPAI_ALPHA",
    }
