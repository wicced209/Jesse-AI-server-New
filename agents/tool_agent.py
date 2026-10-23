"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  CRSMCPAI Alpha — Tool Agent (ARC Execution)                                 ║
║  Owns ARC tool execution: receives tool tasks from the orchestrator,         ║
║  validates them through the Guardian Agent, dispatches to the 16 ARC         ║
║  tools via the ArcRegistry, and returns structured results.                  ║
║  Owner: SLMK Jesse Martinez Junior                                           ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
from core.logger import log_event
from memory.ledger import create_event
from agents.guardian_agent import guardian_agent
from api.arc_tools import ArcRegistry

# Process-wide registry (same pattern as api/server.py's _arc_registry).
_registry = None


def _get_registry() -> ArcRegistry:
    global _registry
    if _registry is None:
        _registry = ArcRegistry()
    return _registry


def _infer_tool_id(task: str, registry: ArcRegistry):
    """Match a tool task to an ARC tool_id (or name) mentioned in it."""
    lower = task.lower()
    for desc in registry.list_tools():
        tool_id = desc.get("tool_id", "")
        if tool_id and tool_id.lower() in lower:
            return tool_id
        name = desc.get("name", "")
        if name and name.lower() in lower:
            return tool_id
    return None


def tool_agent(task: str, tool_id: str = None, action: str = None,
               params: dict = None, user: str = "jesse_martinez_jr") -> dict:
    """
    Execute an ARC tool task.

    Flow: Guardian validation (authenticate + sign + PQSVM verify) ->
    ArcRegistry.operate() dispatch -> sealed, structured result.
    With no explicit tool_id, one is inferred from the task text; if no
    tool matches, the available tool list is returned undispatched.
    """
    log_event(f"[TOOL] Task received: {task} | tool_id={tool_id} "
              f"action={action} | User: {user}")
    registry = _get_registry()

    if tool_id is None:
        tool_id = _infer_tool_id(task, registry)
    if tool_id is None:
        log_event("[TOOL] No ARC tool matched the task; returning tool list",
                  "warning")
        return {
            "agent": "tool",
            "task": task,
            "status": "needs_tool",
            "available": [d.get("tool_id") for d in registry.list_tools()],
        }

    if action is None:
        described = registry.describe(tool_id)
        if not described.get("ok"):
            return {"agent": "tool", "task": task, "tool_id": tool_id,
                    "status": "unknown_tool", "error": described.get("error")}
        supported = described.get("supported_actions") or []
        action = supported[0] if supported else "status"

    # ── Guardian validation (the codebase's validation path) ──────────────
    validation = guardian_agent(f"tool:{tool_id}:{action}:{task}", user)
    if validation.get("status") != "verified":
        log_event(f"[TOOL] Guardian validation FAILED for {tool_id}: "
                  f"{validation.get('status')}", "warning")
        create_event({"agent": "tool", "tool_id": tool_id, "action": action,
                      "task": task[:80], "status": "validation_failed"})
        return {
            "agent": "tool",
            "task": task,
            "tool_id": tool_id,
            "action": action,
            "status": "validation_failed",
            "validation": validation,
        }

    # ── Dispatch to the ARC tool ───────────────────────────────────────────
    result = registry.operate(tool_id, action, params or {}, user)
    status = "executed" if result.get("ok") else "tool_error"
    create_event({"agent": "tool", "tool_id": tool_id, "action": action,
                  "task": task[:80], "status": status})
    log_event(f"[TOOL] {tool_id}.{action} -> {status}")

    return {
        "agent": "tool",
        "task": task,
        "tool_id": tool_id,
        "action": action,
        "validation": validation,
        "result": result,
        "status": status,
    }
