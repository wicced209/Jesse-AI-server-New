"""
Cross platform routing table.
Owner: SLMK Jesse Martinez Junior
"""
import time
from core.config import SOVEREIGN_OWNER
from core.logger import log_event


class CrossPlatformRoutingTable:
    MODULE_ID = "cross_platform_routing_table"
    OWNER = SOVEREIGN_OWNER

    def __init__(self):
        self._table = {
            "ios": "solva_voice",
            "android": "solva_voice",
            "web": "demo_lane",
            "cli": "dominion_cli",
            "mesh": "sin_network",
            "relay": "relay_supervisor",
        }
        self._boot = time.time()
        log_event(f"[{self.MODULE_ID}] initialized routes={len(self._table)}")

    def status(self):
        return {
            "module": self.MODULE_ID,
            "owner": self.OWNER,
            "status": "LIVE",
            "routes": len(self._table),
            "table": dict(self._table),
        }

    def operate(self, payload=None):
        payload = payload or {}
        platform = str(payload.get("platform", "web")).lower()
        target = self._table.get(platform, "dominion_core")
        if "set" in payload and payload.get("target"):
            self._table[platform] = payload["target"]
            target = payload["target"]
        return {
            "module": self.MODULE_ID,
            "owner": self.OWNER,
            "platform": platform,
            "routed_to": target,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
