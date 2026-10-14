"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  CRSMCPAI Alpha — Planner Agent (Structured)                                 ║
║  Decomposes tasks into machine-actionable steps for the autonomous loop.     ║
║  Owner: SLMK Jesse Martinez Junior                                           ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import re
from core.logger import log_event
from models.ollama_runtime import generate

PLANNER_SYSTEM = """You are the Planner Agent inside CRSMCPAI Alpha, the sovereign
AGI stack owned by SLMK Jesse Martinez Junior.

Break the task into concrete, ordered steps. Rules:
- Output ONLY a numbered list. One step per line.
- Each step must be a single self-contained Python coding task that the
  Builder Agent can implement and run inside a restricted sandbox
  (math, datetime, json, re, hashlib allowed; no files, no network).
- Keep steps small: 1-5 steps total.
- No explanations outside the numbered list."""


def _parse_steps(plan_text: str) -> list:
    """Extract numbered steps from planner output."""
    steps = []
    for line in plan_text.splitlines():
        m = re.match(r"^\s*(?:\d+[\).\:]|[-*])\s*(.+)$", line.strip())
        if m:
            steps.append(m.group(1).strip())
    # Fallback: non-empty lines.
    if not steps:
        steps = [l.strip() for l in plan_text.splitlines() if l.strip()][:5]
    return steps[:5]


def planner_agent(task: str) -> dict:
    """
    Plans a multi-step approach. Returns structured steps the
    autonomous loop can execute one by one.
    """
    log_event(f"[PLANNER] Task received: {task}")

    prompt = f"{PLANNER_SYSTEM}\n\nTask: {task}\n"
    try:
        plan_text = generate(prompt)
    except Exception as e:
        log_event(f"[PLANNER] LLM unavailable, using stub plan. Error: {e}", "warning")
        plan_text = f"1. Analyze the task: {task}\n2. Implement the solution in Python.\n3. Verify the output."

    steps = _parse_steps(plan_text)
    log_event(f"[PLANNER] Plan complete: {len(steps)} steps")

    return {
        "agent": "planner",
        "task": task,
        "plan": plan_text,
        "steps": steps,
        "step_count": len(steps),
        "status": "planned",
    }
