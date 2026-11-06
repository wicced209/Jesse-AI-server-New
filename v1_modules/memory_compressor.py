"""Memory compressor — v1 module. Owner: SLMK Jesse Martinez Junior"""
import hashlib
import json
import time
from core.config import SOVEREIGN_OWNER


class MemoryCompressor:
    MODULE_ID = "memory_compressor"
    OWNER = SOVEREIGN_OWNER

    def status(self):
        return {"module": self.MODULE_ID, "owner": self.OWNER, "status": "LIVE"}

    def compress(self, records: list) -> dict:
        raw = json.dumps(records, sort_keys=True)
        # Extractive compression: keep first/last + hash of middle
        if len(records) <= 4:
            summary = records
        else:
            summary = records[:2] + [{"_compressed_span": len(records) - 4,
                                      "mid_hash": hashlib.sha3_256(
                                          json.dumps(records[2:-2], sort_keys=True).encode()
                                      ).hexdigest()[:16]}] + records[-2:]
        return {
            "module": self.MODULE_ID,
            "owner": self.OWNER,
            "original_count": len(records),
            "compressed_count": len(summary),
            "ratio": round(len(summary) / max(len(records), 1), 3),
            "summary": summary,
            "raw_sha3": hashlib.sha3_256(raw.encode()).hexdigest()[:16],
            "ts": time.time(),
        }
