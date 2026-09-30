"""
MCP — Module Context Protocol
Defines how agents register, communicate, and share context.
"""
from core.logger import log_event


class ModuleContextProtocol:
    """
    Central broker for inter-agent context passing.
    Agents register themselves and publish/subscribe to context events.
    """

    def __init__(self):
        self._registry: dict[str, dict] = {}
        self._message_bus: list[dict]   = []

    def register_module(self, name: str, capabilities: list[str]):
        """Register an agent/module and its capabilities."""
        self._registry[name] = {
            "name":         name,
            "capabilities": capabilities,
            "status":       "active",
        }
        log_event(f"[MCP] Module registered: {name} | caps: {capabilities}")

    def publish(self, sender: str, event_type: str, payload: dict):
        """Publish a context event to the bus."""
        message = {
            "sender":     sender,
            "event_type": event_type,
            "payload":    payload,
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


# Singleton instance
mcp = ModuleContextProtocol()

# Auto-register core agents
for _agent in ["planner", "builder", "guardian", "memory"]:
    mcp.register_module(_agent, ["context", "command", "result"])
