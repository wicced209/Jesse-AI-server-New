"""
CRS — Context Reasoning System (v2, 2026-11-08, Muse).

v1 kept a rolling list of entries and could print them back. That is
a buffer, not a reasoning system. v2 keeps the v1 API (push,
get_context, summarize, clear, and the shared `crs` singleton) and
gives the system its actual functions:

  * Retrieval — every entry is embedded with the memory harness's
    local embedder (memory/vector_store.py) at push time, and
    retrieve() recalls entries by cosine similarity to a query, so
    relevant context from far back in the window can be found instead
    of only the most recent turns.
  * Assembly — assemble() builds the working context for a question:
    the entries most relevant to it, plus the most recent entries,
    deduplicated and ordered, with the scores that chose them.
  * Reasoning — reason() grounds the AGSSI three-pass pipeline in
    the assembled context and returns its verdict untouched. When
    the relay is unavailable, reason() returns the assembled context
    with status relay_unavailable and NO fabricated answer — the
    context work is real even when the voice is not there to use it.

The context window is working memory by design: it lives in-process,
like v1. Durable memory lives in the conversation store, the vector
store, and the Golden Ledger; CRS is where the stack thinks with
what it remembers.

Owner: SLMK Jesse Martinez Junior.
"""
import time

from core.logger import log_event

_MIN_SCORE = 0.10


class ContextReasoningSystem:
    """Working context with embedding retrieval and grounded
    reasoning. v1 API preserved."""

    def __init__(self, max_context: int = 64):
        self._context: list[dict] = []
        self.max_context = max_context
        self._seq = 0

    # ── v1 API ─────────────────────────────────────────────────────

    def push(self, role: str, content: str):
        """Add an entry to the context window (now embedded for
        retrieval as it lands)."""
        from memory.vector_store import embed_text
        self._seq += 1
        entry = {"id": self._seq, "role": role, "content": content,
                 "ts": time.time(), "embedding": embed_text(content or "")}
        self._context.append(entry)
        if len(self._context) > self.max_context:
            self._context.pop(0)
        log_event(f"[CRS] Context updated — {len(self._context)} entries")

    def get_context(self) -> list[dict]:
        return [{"role": e["role"], "content": e["content"]}
                for e in self._context]

    def summarize(self) -> str:
        """Return a flat string summary of the current context."""
        return "\n".join(
            f"[{e['role'].upper()}] {e['content']}"
            for e in self._context
        )

    def clear(self):
        self._context.clear()
        log_event("[CRS] Context cleared")

    # ── v2: retrieval, assembly, reasoning ─────────────────────────

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        """Recall the entries most relevant to a query, scored by the
        same cosine math the vector memory uses."""
        from memory.vector_store import _cosine, embed_text
        if not query or not self._context:
            return []
        qv = embed_text(query)
        scored = []
        for e in self._context:
            score = _cosine(qv, e["embedding"])
            if score >= _MIN_SCORE:
                scored.append({"id": e["id"], "role": e["role"],
                               "content": e["content"], "score": round(score, 4)})
        scored.sort(key=lambda r: r["score"], reverse=True)
        return scored[:top_k]

    def assemble(self, query: str, recent: int = 4, top_k: int = 5) -> dict:
        """Build the working context for a question: relevant entries
        plus the most recent ones, deduplicated, in window order,
        with the retrieval scores kept for audit."""
        relevant = self.retrieve(query, top_k=top_k)
        recent_entries = self._context[-recent:] if recent > 0 else []
        chosen = {r["id"]: r for r in relevant}
        for e in recent_entries:
            if e["id"] not in chosen:
                chosen[e["id"]] = {"id": e["id"], "role": e["role"],
                                   "content": e["content"], "score": None}
        ordered = [chosen[k] for k in sorted(chosen)]
        return {"query": query, "entries": ordered,
                "retrieved": len(relevant), "recent": len(recent_entries),
                "window_size": len(self._context)}

    def reason(self, query: str) -> dict:
        """Ground the AGSSI pipeline in the assembled context and
        return its verdict. Offline, the assembled context is
        returned with relay_unavailable and no invented answer."""
        from api.agssi_core import reason as agssi_reason
        assembled = self.assemble(query)
        if not assembled["entries"]:
            return {"query": query, "status": "no_context",
                    "assembled": assembled, "answer": None}
        context_text = "\n".join(
            f"[{e['role']}] {e['content']}" for e in assembled["entries"])
        grounded = (f"Context from the working window:\n{context_text}\n\n"
                    f"Question: {query}")
        verdict = agssi_reason(grounded)
        return {"query": query, "status": verdict.get("status"),
                "assembled": assembled, "verdict": verdict,
                "answer": verdict.get("final_answer")}

    def stats(self) -> dict:
        return {"entries": len(self._context), "max_context": self.max_context,
                "oldest_id": self._context[0]["id"] if self._context else None,
                "newest_id": self._context[-1]["id"] if self._context else None}


# Singleton instance shared across the system
crs = ContextReasoningSystem()
