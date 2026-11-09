"""
MCP — Module Context Protocol (v2, 2026-11-08, Muse).

Defines how agents register, communicate, and share context. v1 was
a registry plus an append-only message list: modules could register
and publish, but nothing could be CALLED through the protocol and no
consumer could track what it had already read. v2 keeps the v1 API
(register_module, publish, consume, list_modules, and the shared
`mcp` singleton with the six core agents auto-registered) and adds
the working half of a protocol:

  * Callable handlers — register_handler() binds a name to a real
    function; dispatch() invokes it through the protocol and returns
    a result envelope with timing. Handler exceptions are caught and
    returned as error envelopes, never raised into callers.
  * Cursor consumption — consume_since(cursor) lets a consumer read
    only the bus messages it has not seen, so the bus can be polled
    without re-processing history.
  * Built-in read handlers for the live stack (ledger_status,
    telemetry_status, sentinel_scan, sync_state, os_family_status,
    networks_status), registered at import, each a thin call into
    the real module — the protocol's first working tool surface.

Every dispatch is published to the bus as an auditable event.

Owner: SLMK Jesse Martinez Junior.
"""
import time

from core.logger import log_event


class ModuleContextProtocol:
    """Central broker for inter-agent context passing and calls."""

    def __init__(self):
        self._registry: dict[str, dict] = {}
        self._message_bus: list[dict] = []
        self._handlers: dict[str, dict] = {}
        self._seq = 0

    # ── v1 API ─────────────────────────────────────────────────────

    def register_module(self, name: str, capabilities: list[str]):
        """Register an agent/module and its capabilities."""
        self._registry[name] = {
            "name": name,
            "capabilities": capabilities,
            "status": "active",
        }
        log_event(f"[MCP] Module registered: {name} | caps: {capabilities}")

    def publish(self, sender: str, event_type: str, payload: dict):
        """Publish a context event to the bus."""
        self._seq += 1
        message = {
            "seq": self._seq,
            "sender": sender,
            "event_type": event_type,
            "payload": payload,
        }
        self._message_bus.append(message)
        log_event(f"[MCP] Event published: {sender} → {event_type}")
        return message

    def consume(self, event_type: str = "") -> list[dict]:
        """Consume messages, optionally filtered by event_type."""
        if not event_type:
            return list(self._message_bus)
        return [m for m in self._message_bus if m["event_type"] == event_type]

    def list_modules(self) -> dict:
        return dict(self._registry)

    # ── v2: cursors, handlers, dispatch ────────────────────────────

    def consume_since(self, cursor: int = 0, event_type: str = "") -> dict:
        """Read only messages after the cursor (a bus sequence
        number). Returns the messages and the new cursor."""
        out = [m for m in self._message_bus
               if m["seq"] > cursor and (not event_type or m["event_type"] == event_type)]
        new_cursor = out[-1]["seq"] if out else cursor
        return {"messages": out, "cursor": new_cursor}

    def register_handler(self, name: str, fn, description: str = ""):
        """Bind a callable tool to the protocol."""
        self._handlers[name] = {"fn": fn, "description": description}
        log_event(f"[MCP] Handler registered: {name}")

    def list_handlers(self) -> dict:
        return {name: {"description": h["description"]}
                for name, h in self._handlers.items()}

    def dispatch(self, name: str, payload: dict = None, caller: str = "") -> dict:
        """Invoke a handler through the protocol. Always returns an
        envelope; failures are reported, never raised."""
        handler = self._handlers.get(name)
        if handler is None:
            return {"ok": False, "handler": name,
                    "error": f"unknown handler '{name}'",
                    "known": sorted(self._handlers)}
        started = time.time()
        try:
            result = handler["fn"](payload or {})
            envelope = {"ok": True, "handler": name, "result": result,
                        "latency_ms": round((time.time() - started) * 1000, 2)}
        except Exception as exc:
            envelope = {"ok": False, "handler": name,
                        "error": f"{type(exc).__name__}: {exc}",
                        "latency_ms": round((time.time() - started) * 1000, 2)}
        self.publish(caller or "mcp", "dispatch",
                     {"handler": name, "ok": envelope["ok"]})
        return envelope


# Singleton instance
mcp = ModuleContextProtocol()

# Auto-register core agents
for _agent in ["planner", "builder", "guardian", "memory", "tool",
               "scheduler"]:
    mcp.register_module(_agent, ["context", "command", "result"])


# ── Built-in read handlers over the live stack ─────────────────────────

def _h_ledger_status(_payload):
    from memory.ledger import get_ledger, verify_chain
    chain = get_ledger()
    return {"height": len(chain), "chain_valid": verify_chain()}


def _h_telemetry_status(_payload):
    from api.telemetry_ingest import ingest_status
    return ingest_status()


def _h_sentinel_scan(_payload):
    from api.sentinel import sentinel_engine
    return sentinel_engine.scan()


def _h_sync_state(_payload):
    from api.hyper_sync import state_vector
    return state_vector()


def _h_os_family_status(_payload):
    from api.os_family import family_status
    return family_status()


def _h_networks_status(_payload):
    from api.networks import all_networks
    return all_networks()


for _name, _fn, _desc in [
    ("ledger_status", _h_ledger_status, "Golden Ledger height and chain validity"),
    ("telemetry_status", _h_telemetry_status, "Telemetry sources, batches, events"),
    ("sentinel_scan", _h_sentinel_scan, "Sentinel threat scan over current events"),
    ("sync_state", _h_sync_state, "Hyper-sync state vector of this node"),
    ("os_family_status", _h_os_family_status, "Six-OS family states and duty results"),
    ("networks_status", _h_networks_status, "SIN/SOLVA/Dominion binding states"),
]:
    mcp.register_handler(_name, _fn, _desc)
