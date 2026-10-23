"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  CRSMCPAI Alpha — Scheduler Agent (Timed / Recurring Execution)              ║
║  Owns timed and recurring execution: schedule registration, due-task         ║
║  detection, and dispatch through the orchestrator (core.router).             ║
║  Recurring schedules re-register on completion — eternal runtime.            ║
║  Owner: SLMK Jesse Martinez Junior                                           ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import time

from core.logger import log_event
from memory.ledger import create_event

# name -> {name, command, interval_s, next_run, recurring, runs, last_status}
_schedules: dict[str, dict] = {}


def register_schedule(name: str, command: str, interval_s: float = None,
                      run_at: float = None, recurring: bool = True) -> dict:
    """
    Register a scheduled command. A recurring schedule requires
    interval_s and re-registers itself after every dispatch
    (eternal runtime); a one-shot schedule fires once at run_at
    (default: now + interval_s, or immediately).
    """
    now = time.time()
    if run_at is None:
        run_at = now + interval_s if interval_s else now
    entry = {
        "name": name,
        "command": command,
        "interval_s": interval_s,
        "next_run": run_at,
        "recurring": bool(recurring and interval_s),
        "runs": 0,
        "last_status": "registered",
    }
    _schedules[name] = entry
    create_event({"agent": "scheduler", "action": "register", "name": name,
                  "command": command[:80], "interval_s": interval_s,
                  "recurring": entry["recurring"]})
    log_event(f"[SCHEDULER] Registered '{name}' -> {command[:60]} "
              f"(interval={interval_s}, recurring={entry['recurring']})")
    return dict(entry)


def cancel_schedule(name: str) -> dict:
    """Remove a schedule by name."""
    entry = _schedules.pop(name, None)
    if entry is None:
        return {"agent": "scheduler", "action": "cancel", "name": name,
                "status": "not_found"}
    create_event({"agent": "scheduler", "action": "cancel", "name": name})
    log_event(f"[SCHEDULER] Cancelled '{name}'")
    return {"agent": "scheduler", "action": "cancel", "name": name,
            "status": "cancelled"}


def list_schedules() -> list:
    """All registered schedules (copies)."""
    return [dict(e) for e in _schedules.values()]


def due_schedules(now: float = None) -> list:
    """Schedules whose next_run has arrived (detection only, no dispatch)."""
    now = time.time() if now is None else now
    return [dict(e) for e in _schedules.values() if e["next_run"] <= now]


def tick(dispatch=None, user: str = "jesse_martinez_jr") -> dict:
    """
    Detect due schedules and dispatch each through the orchestrator.
    Default dispatch is core.router.route_command (imported lazily —
    router imports this package). Recurring schedules re-register on
    completion: next_run = completion time + interval (eternal runtime).
    One-shot schedules are marked complete and removed.
    """
    if dispatch is None:
        from core.router import route_command
        dispatch = route_command

    now = time.time()
    fired = []
    for entry in list(_schedules.values()):
        if entry["next_run"] > now:
            continue
        log_event(f"[SCHEDULER] Due: '{entry['name']}' -> "
                  f"{entry['command'][:60]}")
        try:
            outcome = dispatch(entry["command"], user)
            status = outcome.get("status", "dispatched") \
                if isinstance(outcome, dict) else "dispatched"
        except Exception as e:
            status = "dispatch_failed"
            log_event(f"[SCHEDULER] Dispatch failed for "
                      f"'{entry['name']}': {e}", "warning")
        entry["runs"] += 1
        entry["last_status"] = status
        fired.append({"name": entry["name"], "command": entry["command"],
                      "status": status, "runs": entry["runs"]})
        create_event({"agent": "scheduler", "action": "dispatch",
                      "name": entry["name"], "status": status,
                      "runs": entry["runs"]})
        if entry["recurring"]:
            # Eternal runtime: re-register on completion.
            entry["next_run"] = time.time() + entry["interval_s"]
        else:
            _schedules.pop(entry["name"], None)

    return {"agent": "scheduler", "action": "tick", "fired": fired,
            "fired_count": len(fired), "status": "ticked"}


def scheduler_agent(task: str, action: str = None, name: str = None,
                    command: str = None, interval_s: float = None,
                    recurring: bool = True,
                    user: str = "jesse_martinez_jr") -> dict:
    """
    Scheduler Agent entry point (same convention as the other agents).

    Actions: "register" (needs name + command), "cancel" (name),
    "list", "tick" (detect + dispatch due schedules), "status"
    (report only — the default for a plain command string, so an
    orchestrator pass never dispatches as a side effect).
    """
    log_event(f"[SCHEDULER] Task received: {task} | action={action}")

    if action is None:
        lower = task.lower()
        if "list" in lower:
            action = "list"
        elif "cancel" in lower or "remove" in lower:
            action = "cancel"
        elif "tick" in lower or "run due" in lower:
            action = "tick"
        elif "register" in lower:
            action = "register"
        else:
            action = "status"

    if action == "register":
        if not name:
            return {"agent": "scheduler", "task": task,
                    "status": "needs_name"}
        entry = register_schedule(name, command or task,
                                  interval_s=interval_s,
                                  recurring=recurring)
        return {"agent": "scheduler", "task": task, "action": "register",
                "schedule": entry, "status": "registered"}

    if action == "cancel":
        if not name:
            return {"agent": "scheduler", "task": task,
                    "status": "needs_name"}
        result = cancel_schedule(name)
        result.update({"task": task})
        return result

    if action == "list":
        schedules = list_schedules()
        return {"agent": "scheduler", "task": task, "action": "list",
                "count": len(schedules), "schedules": schedules,
                "status": "listed"}

    if action == "tick":
        result = tick(user=user)
        result.update({"task": task})
        return result

    schedules = list_schedules()
    return {"agent": "scheduler", "task": task, "action": "status",
            "count": len(schedules), "schedules": schedules,
            "due_count": len(due_schedules()), "status": "reported"}
