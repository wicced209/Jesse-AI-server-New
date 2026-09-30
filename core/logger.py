"""Core logger — structured event logging for Jesse AI sovereign stack."""
import time

_event_log: list[dict] = []


def log_event(message: str, level: str = "info") -> dict:
    """Log a sovereign system event."""
    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "level":     level.upper(),
        "message":   message,
    }
    _event_log.append(entry)
    ts = entry["timestamp"]
    print(f"[{ts}] [{level.upper():7s}] {message}")
    return entry


def get_log() -> list[dict]:
    return list(_event_log)
