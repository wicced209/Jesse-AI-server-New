"""
CRSMCPAI Alpha - CRS Sovereign Operating System Kernel Layer

Kernel abstraction serving the six sovereign OSes
(Genesis, Phoenix, Consciousness, Dominion, Sovereign, Sovereign Dominion):
- Task/process table with lifecycle states
- Priority scheduler tick (deterministic)
- Inter-process message queues (IPC mailboxes)
- Capability/permission checks per task
- Kernel event log ring buffer

Crash-proof guarantees:
- Standard library only (time, collections)
- NO FastAPI / web imports
- NO module-level I/O
- All methods defensive: bad input handled safely, never raises

Built per Jesse AI specification, supreme hyper immaculate God mode standards.
Owner: SLMK Jesse Martinez Junior.
"""

import time
from collections import deque

GENESIS_HASH = "92038cafccc7192535bd475cca985d03000d89962b8dc96f6664081663559b1b"

# OS variants served by this kernel layer
OS_VARIANTS = ("GENESIS", "PHOENIX", "CONSCIOUSNESS", "DOMINION",
               "SOVEREIGN", "SOVEREIGN_DOMINION")

# Task states
TASK_STATES = ("READY", "RUNNING", "BLOCKED", "TERMINATED")

# Capabilities
CAPABILITIES = ("SYS_EXEC", "SYS_IPC", "SYS_MEM", "SYS_NET",
                "SYS_LEDGER", "SYS_ADMIN")

MAX_TASKS = 256
MAX_MAILBOX = 64
LOG_CAPACITY = 256


def _safe_str(v, default=""):
    try:
        return str(v) if v is not None else default
    except Exception:
        return default


class TaskControlBlock:
    """Per-task kernel record."""

    def __init__(self, pid, name, os_variant, priority, capabilities):
        self.pid = pid
        self.name = _safe_str(name, f"task-{pid}")
        self.os_variant = os_variant if os_variant in OS_VARIANTS else "GENESIS"
        try:
            self.priority = int(priority)
        except Exception:
            self.priority = 10
        self.priority = max(0, min(self.priority, 255))
        caps = set()
        try:
            for c in (capabilities or ()):
                cs = _safe_str(c)
                if cs in CAPABILITIES:
                    caps.add(cs)
        except Exception:
            pass
        if not caps:
            caps = {"SYS_EXEC", "SYS_IPC"}
        self.capabilities = caps
        self.state = "READY"
        self.mailbox = deque()
        self.spawn_tick = 0
        self.run_ticks = 0

    def to_dict(self):
        try:
            return {
                "pid": self.pid,
                "name": self.name,
                "os_variant": self.os_variant,
                "priority": self.priority,
                "capabilities": sorted(self.capabilities),
                "state": self.state,
                "mailbox_depth": len(self.mailbox),
                "run_ticks": self.run_ticks,
            }
        except Exception:
            return {"pid": self.pid, "state": "UNKNOWN"}


class SovereignKernel:
    """Deterministic sovereign microkernel."""

    def __init__(self):
        self._tasks = {}
        self._next_pid = 0
        self.current_tick = 0
        self._log = deque(maxlen=LOG_CAPACITY)
        # PID 0: kernel idle task
        idle = TaskControlBlock(0, "kernel-idle", "GENESIS", 255,
                                {"SYS_EXEC", "SYS_IPC"})
        idle.spawn_tick = 0
        self._tasks[0] = idle
        self._next_pid = 1
        self._log_event("KERNEL_INIT", "sovereign kernel online")

    # -- internal --
    def _log_event(self, etype, detail):
        try:
            self._log.append({
                "tick": self.current_tick,
                "type": _safe_str(etype, "EVENT"),
                "detail": _safe_str(detail)[:256],
            })
        except Exception:
            pass

    def _get(self, pid):
        try:
            return self._tasks.get(int(pid))
        except Exception:
            return None

    # -- task management --
    def spawn_task(self, name, os_variant="GENESIS", priority=10, capabilities=None):
        """Create a task. Returns pid, or -1 on failure."""
        try:
            if len(self._tasks) >= MAX_TASKS:
                self._log_event("SPAWN_DENIED", "task table full")
                return -1
            pid = self._next_pid
            self._next_pid += 1
            tcb = TaskControlBlock(pid, name, os_variant, priority, capabilities)
            tcb.spawn_tick = self.current_tick
            self._tasks[pid] = tcb
            self._log_event("SPAWN", f"pid={pid} name={tcb.name} os={tcb.os_variant}")
            return pid
        except Exception:
            return -1

    def kill_task(self, pid):
        """Terminate a task. PID 0 (idle) cannot be killed."""
        try:
            t = self._get(pid)
            if t is None or t.pid == 0:
                return False
            t.state = "TERMINATED"
            try:
                t.mailbox.clear()
            except Exception:
                pass
            self._log_event("KILL", f"pid={t.pid}")
            return True
        except Exception:
            return False

    def check_capability(self, pid, required_cap):
        """True if task holds the capability and is not terminated."""
        try:
            t = self._get(pid)
            if t is None or t.state == "TERMINATED":
                return False
            cap = _safe_str(required_cap)
            ok = cap in t.capabilities
            if not ok:
                self._log_event("CAP_DENIED", f"pid={t.pid} cap={cap}")
            return ok
        except Exception:
            return False

    # -- IPC --
    def send_ipc(self, sender_pid, receiver_pid, msg_type, payload):
        """Queue a message into the receiver's mailbox. Never raises."""
        try:
            s = self._get(sender_pid)
            r = self._get(receiver_pid)
            if s is None or r is None:
                return False
            if s.state == "TERMINATED" or r.state == "TERMINATED":
                return False
            if "SYS_IPC" not in s.capabilities:
                self._log_event("IPC_DENIED", f"sender={s.pid} no SYS_IPC")
                return False
            if len(r.mailbox) >= MAX_MAILBOX:
                self._log_event("IPC_DROPPED", f"receiver={r.pid} mailbox full")
                return False
            try:
                pl = dict(payload) if isinstance(payload, dict) else {"data": _safe_str(payload)[:512]}
            except Exception:
                pl = {}
            r.mailbox.append({
                "from": s.pid,
                "to": r.pid,
                "type": _safe_str(msg_type, "MSG")[:64],
                "payload": pl,
                "tick": self.current_tick,
            })
            self._log_event("IPC", f"{s.pid}->{r.pid} {_safe_str(msg_type, 'MSG')[:32]}")
            return True
        except Exception:
            return False

    def receive_ipc(self, receiver_pid):
        """Pop the oldest message from a task's mailbox. None if empty."""
        try:
            r = self._get(receiver_pid)
            if r is None or r.state == "TERMINATED":
                return None
            if not r.mailbox:
                return None
            return r.mailbox.popleft()
        except Exception:
            return None

    # -- scheduler --
    def scheduler_tick(self):
        """Run one deterministic scheduling tick.

        Picks the highest-priority READY task (lowest priority number wins
        ties by lowest pid), marks it RUNNING for the tick, then READY again.
        Returns the selected pid (0 = idle).
        """
        try:
            self.current_tick += 1
            best = None
            for pid in sorted(self._tasks.keys()):
                t = self._tasks[pid]
                if t.state == "READY" and pid != 0:
                    if best is None or (t.priority, t.pid) < (best.priority, best.pid):
                        best = t
            if best is None:
                best = self._tasks.get(0)
            if best is None:
                return 0
            best.state = "RUNNING"
            best.run_ticks += 1
            # tasks blocked on empty mailbox stay blocked; others run one tick
            best.state = "READY"
            return best.pid
        except Exception:
            return 0

    def block_task(self, pid):
        try:
            t = self._get(pid)
            if t is None or t.pid == 0:
                return False
            t.state = "BLOCKED"
            self._log_event("BLOCK", f"pid={t.pid}")
            return True
        except Exception:
            return False

    def unblock_task(self, pid):
        try:
            t = self._get(pid)
            if t is None or t.state != "BLOCKED":
                return False
            t.state = "READY"
            self._log_event("UNBLOCK", f"pid={t.pid}")
            return True
        except Exception:
            return False

    # -- introspection --
    def get_kernel_status(self):
        """Snapshot of kernel state. Never raises."""
        try:
            states = {}
            by_os = {}
            for t in self._tasks.values():
                states[t.state] = states.get(t.state, 0) + 1
                by_os[t.os_variant] = by_os.get(t.os_variant, 0) + 1
            return {
                "kernel": "CRS_SOVEREIGN_KERNEL",
                "status": "ACTIVE",
                "genesis": GENESIS_HASH[:16],
                "tick": self.current_tick,
                "task_count": len(self._tasks),
                "states": states,
                "by_os_variant": by_os,
                "os_variants": list(OS_VARIANTS),
                "log_depth": len(self._log),
            }
        except Exception:
            return {"kernel": "CRS_SOVEREIGN_KERNEL", "status": "UNKNOWN"}

    def get_task_table(self):
        try:
            return [t.to_dict() for _, t in sorted(self._tasks.items())]
        except Exception:
            return []

    def get_event_log(self, limit=50):
        try:
            n = max(1, min(int(limit), LOG_CAPACITY))
        except Exception:
            n = 50
        try:
            return list(self._log)[-n:]
        except Exception:
            return []


def module_status():
    return {
        "module": "crs.sovereign_os_kernel",
        "status": "ACTIVE",
        "genesis": GENESIS_HASH[:16],
        "os_variants": list(OS_VARIANTS),
        "capabilities": list(CAPABILITIES),
        "functions": [
            "SovereignKernel.spawn_task",
            "SovereignKernel.kill_task",
            "SovereignKernel.check_capability",
            "SovereignKernel.send_ipc",
            "SovereignKernel.receive_ipc",
            "SovereignKernel.scheduler_tick",
            "SovereignKernel.get_kernel_status",
        ],
    }
