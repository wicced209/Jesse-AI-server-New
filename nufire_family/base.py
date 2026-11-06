"""
Base class for every NUFIRE / Tara Infinity family module.
Owner: SLMK Jesse Martinez Junior
"""
import hashlib
import time
from core.config import SOVEREIGN_OWNER
from core.logger import log_event


class FamilyModule:
    """Standard contract for all family members."""

    MODULE_ID = "FAMILY_BASE"
    MODULE_VER = "1.0.0"
    OWNER = SOVEREIGN_OWNER
    FAMILY = "NUFIRE_TARA_INFINITY"

    def __init__(self):
        self._ops = 0
        self._boot = time.time()
        log_event(f"[{self.MODULE_ID}] initialized — owner={self.OWNER}")

    def status(self) -> dict:
        return {
            "module": self.MODULE_ID,
            "version": self.MODULE_VER,
            "family": self.FAMILY,
            "owner": self.OWNER,
            "status": "LIVE",
            "ops": self._ops,
            "uptime_s": round(time.time() - self._boot, 3),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    def operate(self, payload: dict | None = None) -> dict:
        payload = payload or {}
        self._ops += 1
        seed = hashlib.sha3_256(
            f"{self.MODULE_ID}:{payload}:{time.time()}".encode()
        ).hexdigest()
        result = {
            "module": self.MODULE_ID,
            "owner": self.OWNER,
            "op_id": seed[:16],
            "input": payload,
            "output": self._compute(payload, seed),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        return result

    def _compute(self, payload: dict, seed: str) -> dict:
        """Override in subclasses for real work."""
        return {"seed": seed[:32], "note": "base passthrough"}
