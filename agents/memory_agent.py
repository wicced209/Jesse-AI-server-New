from core.logger import log_event
from memory.vector_store import store_memory, retrieve_memory
from memory.ledger import create_event


def memory_agent(task: str) -> dict:
    """
    Stores and retrieves contextual memory.
    Every store action is recorded in the immutable ledger.
    """
    log_event(f"[MEMORY] Task received: {task}")

    lower = task.lower()

    # ── Recall / Retrieve ──────────────────────────────────────────────────
    if "recall" in lower or "retrieve" in lower:
        memories = retrieve_memory()
        log_event(f"[MEMORY] Retrieved {len(memories)} memory entries")
        return {
            "agent":    "memory",
            "action":   "retrieve",
            "count":    len(memories),
            "memories": memories,
            "status":   "retrieved",
        }

    # ── Store ──────────────────────────────────────────────────────────────
    store_memory(task)
    create_event({"agent": "memory", "task": task})
    log_event(f"[MEMORY] Stored and ledger updated")

    return {
        "agent":  "memory",
        "action": "store",
        "task":   task,
        "status": "stored",
    }
