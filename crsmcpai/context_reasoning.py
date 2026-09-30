"""
CRS — Context Reasoning System
Provides multi-step reasoning over a working context window.
"""
from core.logger import log_event


class ContextReasoningSystem:
    """
    Maintains a rolling context of prior inputs and inferences.
    Used by agents to reason across multiple turns.
    """

    def __init__(self, max_context: int = 64):
        self._context: list[dict] = []
        self.max_context = max_context

    def push(self, role: str, content: str):
        """Add an entry to the context window."""
        self._context.append({"role": role, "content": content})
        if len(self._context) > self.max_context:
            self._context.pop(0)
        log_event(f"[CRS] Context updated — {len(self._context)} entries")

    def get_context(self) -> list[dict]:
        return list(self._context)

    def summarize(self) -> str:
        """Return a flat string summary of the current context."""
        return "\n".join(
            f"[{e['role'].upper()}] {e['content']}"
            for e in self._context
        )

    def clear(self):
        self._context.clear()
        log_event("[CRS] Context cleared")


# Singleton instance shared across the system
crs = ContextReasoningSystem()
