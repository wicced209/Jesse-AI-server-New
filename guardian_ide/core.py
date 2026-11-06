"""
Guardian IDE core — metacognition + recursive build loop.
Owner: SLMK Jesse Martinez Junior
"""
import hashlib
import time
from core.config import SOVEREIGN_OWNER
from core.logger import log_event


class GuardianIDE:
    MODULE_ID = "guardian_ide"
    OWNER = SOVEREIGN_OWNER

    def __init__(self):
        self._sessions = {}
        self._recursion_depth = 0
        self._max_depth = 8
        log_event(f"[{self.MODULE_ID}] initialized — metacognition active")

    def status(self):
        return {
            "module": self.MODULE_ID,
            "owner": self.OWNER,
            "status": "LIVE",
            "sessions": len(self._sessions),
            "max_recursion": self._max_depth,
            "features": ["metacognition", "recursive_build", "plan_reflect_act", "owner_gate"],
        }

    def start_session(self, goal: str) -> dict:
        sid = hashlib.sha3_256(f"{goal}|{time.time()}".encode()).hexdigest()[:12]
        self._sessions[sid] = {
            "goal": goal,
            "steps": [],
            "reflections": [],
            "created": time.time(),
            "owner": self.OWNER,
        }
        return {"session_id": sid, "goal": goal, "owner": self.OWNER}

    def metacognize(self, session_id: str, observation: str) -> dict:
        if session_id not in self._sessions:
            return {"ok": False, "error": "session not found"}
        s = self._sessions[session_id]
        reflection = {
            "observation": observation,
            "depth": self._recursion_depth,
            "ts": time.time(),
            "token": hashlib.sha3_256(observation.encode()).hexdigest()[:16],
        }
        s["reflections"].append(reflection)
        return {"ok": True, "reflection": reflection, "session": session_id}

    def recursive_build(self, session_id: str, task: str, depth: int = 0) -> dict:
        if session_id not in self._sessions:
            return {"ok": False, "error": "session not found"}
        if depth > self._max_depth:
            return {"ok": False, "error": "max recursion depth", "depth": depth}
        self._recursion_depth = depth
        step = {
            "task": task,
            "depth": depth,
            "plan": f"plan_for:{task[:40]}",
            "result_token": hashlib.sha3_256(f"{task}|{depth}".encode()).hexdigest()[:16],
            "ts": time.time(),
        }
        self._sessions[session_id]["steps"].append(step)
        # One level of self-call for demonstration of recursion control
        if depth < 1:
            child = self.recursive_build(session_id, f"sub:{task}", depth + 1)
            step["child"] = child.get("step")
        return {"ok": True, "step": step, "session": session_id}

    def session_status(self, session_id: str) -> dict:
        s = self._sessions.get(session_id)
        if not s:
            return {"ok": False, "error": "not found"}
        return {"ok": True, "session": s}


guardian_ide = GuardianIDE()
