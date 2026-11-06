"""Intent classifier — v1 module. Owner: SLMK Jesse Martinez Junior"""
import hashlib
import re
import time
from core.config import SOVEREIGN_OWNER

INTENTS = {
    "command": r"\b(run|execute|build|deploy|audit|status)\b",
    "query": r"\b(what|how|why|when|where|who|status of)\b",
    "directive": r"\b(directive|order|mandate|rebuild)\b",
    "ledger": r"\b(ledger|seal|chain|golden)\b",
    "sovereign": r"\b(sovereign|owner|dominion|jesse)\b",
}


class IntentClassifier:
    MODULE_ID = "intent_classifier"
    OWNER = SOVEREIGN_OWNER

    def status(self):
        return {"module": self.MODULE_ID, "owner": self.OWNER, "status": "LIVE",
                "intents": list(INTENTS.keys())}

    def classify(self, text: str) -> dict:
        text_l = text.lower()
        scores = {}
        for name, pat in INTENTS.items():
            scores[name] = len(re.findall(pat, text_l))
        best = max(scores, key=scores.get) if any(scores.values()) else "unknown"
        return {
            "module": self.MODULE_ID,
            "owner": self.OWNER,
            "text_hash": hashlib.sha3_256(text.encode()).hexdigest()[:16],
            "intent": best,
            "scores": scores,
            "ts": time.time(),
        }
