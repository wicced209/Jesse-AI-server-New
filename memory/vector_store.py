import time

# In-memory store — replace with a real vector DB (Chroma, Qdrant, etc.)
# when you're ready to persist across restarts.
_memory_db: list[dict] = []


def store_memory(data: str) -> dict:
    """Store a text entry with a timestamp."""
    entry = {
        "id":        len(_memory_db) + 1,
        "data":      data,
        "timestamp": time.time(),
    }
    _memory_db.append(entry)
    return entry


def retrieve_memory(query: str = "") -> list[dict]:
    """
    Return all stored memories.
    Optional: filter by query substring (simple keyword match).
    """
    if not query:
        return list(_memory_db)

    q = query.lower()
    return [m for m in _memory_db if q in m["data"].lower()]


def memory_count() -> int:
    return len(_memory_db)
