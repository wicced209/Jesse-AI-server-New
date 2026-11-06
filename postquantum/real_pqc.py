"""
Post-quantum cryptography surface for CRSMCPAI Alpha.
Owner: SLMK Jesse Martinez Junior

IMPORTANT (sandbox honesty rule):
- This sandbox has the 'cryptography' package (classical + some modern primitives)
  but does NOT have liboqs, pqcrypto, or any Kyber / Dilithium / SPHINCS+ / Falcon
  implementation.
- Therefore this module provides:
  1. A clear, honest status that real NIST PQC algorithms are NOT available here.
  2. Interfaces and registration hooks ready for a real PQC backend.
  3. Classical strong primitives (Ed25519 via PyNaCl, SHA3) for interim sealing.
- Never labels a hash or classical signature as "Kyber" or "Dilithium".
"""
import hashlib
import time
from core.config import SOVEREIGN_OWNER
from core.logger import log_event

try:
    from nacl.signing import SigningKey, VerifyKey
    from nacl.exceptions import BadSignatureError
    NACL_OK = True
except Exception:
    NACL_OK = False

GENESIS = "92038cafccc7192535bd475cca985d03000d89962b8dc96f6664081663559b1b"


class RealPQC:
    MODULE_ID = "real_pqc"
    OWNER = SOVEREIGN_OWNER

    def __init__(self):
        self._boot = time.time()
        self._keys = {}
        log_event(f"[{self.MODULE_ID}] initialized — NACL_OK={NACL_OK}")

    def status(self) -> dict:
        return {
            "module": self.MODULE_ID,
            "owner": self.OWNER,
            "status": "LIVE_INTERIM",
            "real_pqc_available": False,
            "reason": (
                "Sandbox runtime has no liboqs / pqcrypto. "
                "Kyber, Dilithium, SPHINCS+, Falcon, and lattice ZKPs are NOT present. "
                "Do not treat any output of this module as a NIST PQC algorithm."
            ),
            "available_backends": {
                "ed25519_nacl": NACL_OK,
                "sha3_512": True,
            },
            "algorithms_declared_unavailable": [
                "Kyber", "Dilithium", "SPHINCS+", "Falcon", "lattice_zkp"
            ],
            "next_step": "Install liboqs-python or pqcrypto in a full runtime, then bind here.",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    def generate_interim_signing_key(self, label: str = "default") -> dict:
        """Ed25519 only — classical, not post-quantum. Labeled honestly."""
        if not NACL_OK:
            return {"ok": False, "error": "PyNaCl not available"}
        sk = SigningKey.generate()
        vk = sk.verify_key
        self._keys[label] = {"sk": sk, "vk": vk}
        return {
            "ok": True,
            "label": label,
            "algorithm": "Ed25519",
            "post_quantum": False,
            "public_key_hex": vk.encode().hex(),
            "note": "Classical signature key. Not Kyber/Dilithium/Falcon.",
        }

    def sign_interim(self, message: bytes, label: str = "default") -> dict:
        if label not in self._keys:
            return {"ok": False, "error": "key label not found"}
        sig = self._keys[label]["sk"].sign(message).signature
        return {
            "ok": True,
            "algorithm": "Ed25519",
            "post_quantum": False,
            "signature_hex": sig.hex(),
            "message_sha3": hashlib.sha3_256(message).hexdigest(),
        }

    def verify_interim(self, message: bytes, signature_hex: str, label: str = "default") -> dict:
        if label not in self._keys:
            return {"ok": False, "error": "key label not found"}
        try:
            self._keys[label]["vk"].verify(message, bytes.fromhex(signature_hex))
            return {"ok": True, "algorithm": "Ed25519", "post_quantum": False}
        except BadSignatureError:
            return {"ok": False, "error": "bad signature"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def kyber_keygen(self, *a, **kw):
        return {
            "ok": False,
            "algorithm": "Kyber",
            "error": "Real Kyber not available in this sandbox. Needs liboqs.",
        }

    def dilithium_sign(self, *a, **kw):
        return {
            "ok": False,
            "algorithm": "Dilithium",
            "error": "Real Dilithium not available in this sandbox. Needs liboqs.",
        }

    def sphincs_sign(self, *a, **kw):
        return {
            "ok": False,
            "algorithm": "SPHINCS+",
            "error": "Real SPHINCS+ not available in this sandbox. Needs liboqs.",
        }

    def falcon_verify(self, *a, **kw):
        return {
            "ok": False,
            "algorithm": "Falcon",
            "error": "Real Falcon not available in this sandbox. Needs liboqs.",
        }

    def lattice_zkp(self, *a, **kw):
        return {
            "ok": False,
            "algorithm": "lattice_zkp",
            "error": "Lattice zero-knowledge proofs not available in this sandbox.",
        }


real_pqc = RealPQC()
