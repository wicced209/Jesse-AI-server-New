"""
Jesse AI — Sovereign Crypto Layer
NaCl Ed25519 signing with graceful fallback for cloud deployment.
Owner: SLMK Jesse Martinez Junior
"""
import hashlib
import os
from core.logger import log_event

try:
    from nacl.signing import SigningKey
    from nacl.encoding import HexEncoder
    _signing_key = SigningKey.generate()
    _verify_key  = _signing_key.verify_key
    public_key   = _verify_key.encode(encoder=HexEncoder).decode()
    NACL_AVAILABLE = True
    log_event(f"[CRYPTO] NaCl Ed25519 active. Public key: {public_key[:32]}...")

    def sign_data(data: bytes) -> str:
        signed = _signing_key.sign(data)
        sig = signed.signature.hex()
        log_event(f"[CRYPTO] Signed {len(data)} bytes (NaCl)")
        return sig

    def get_public_key() -> str:
        return public_key

except ImportError:
    NACL_AVAILABLE = False
    _fallback_key = os.urandom(32).hex()
    public_key = _fallback_key
    log_event("[CRYPTO] NaCl not available — using SHA3-512 fallback signing", "warning")

    def sign_data(data: bytes) -> str:
        sig = hashlib.sha3_512(data + _fallback_key.encode()).hexdigest()
        log_event(f"[CRYPTO] Signed {len(data)} bytes (SHA3 fallback)")
        return sig

    def get_public_key() -> str:
        return _fallback_key
