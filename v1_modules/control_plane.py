"""Control plane — v1 module. Owner: SLMK Jesse Martinez Junior"""
import time
from core.config import SOVEREIGN_OWNER, SYSTEM_NAME, VERSION


class ControlPlane:
    MODULE_ID = "control_plane"
    OWNER = SOVEREIGN_OWNER

    def __init__(self):
        self._commands = []

    def status(self):
        return {
            "module": self.MODULE_ID,
            "owner": self.OWNER,
            "system": SYSTEM_NAME,
            "version": VERSION,
            "status": "LIVE",
            "commands_seen": len(self._commands),
        }

    def issue(self, command: str, issuer: str = "") -> dict:
        if issuer and issuer not in (self.OWNER, "jesse_martinez_jr", "SLMK Jesse Martinez Junior"):
            return {"ok": False, "error": "stranger authority rejected", "issuer": issuer}
        entry = {
            "command": command,
            "issuer": issuer or self.OWNER,
            "ts": time.time(),
            "accepted": True,
        }
        self._commands.append(entry)
        return {"ok": True, "entry": entry, "owner": self.OWNER}
