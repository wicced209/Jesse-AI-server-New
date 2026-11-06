"""Telemetry streamer — v1 module. Owner: SLMK Jesse Martinez Junior"""
import time
from collections import deque
from core.config import SOVEREIGN_OWNER


class TelemetryStreamer:
    MODULE_ID = "telemetry_streamer"
    OWNER = SOVEREIGN_OWNER

    def __init__(self):
        self._buf = deque(maxlen=1000)

    def status(self):
        return {"module": self.MODULE_ID, "owner": self.OWNER, "status": "LIVE",
                "buffered": len(self._buf)}

    def push(self, event: dict) -> dict:
        entry = {"event": event, "ts": time.time(), "owner": self.OWNER}
        self._buf.append(entry)
        return {"ok": True, "buffered": len(self._buf)}

    def stream(self, limit: int = 50) -> dict:
        items = list(self._buf)[-limit:]
        return {"module": self.MODULE_ID, "owner": self.OWNER, "count": len(items),
                "events": items}
