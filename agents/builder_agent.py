"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  CRSMCPAI Alpha — Builder Agent (Autonomous)                                 ║
║  Generates code via the internal LLM and EXECUTES it inside the              ║
║  sovereign sandbox. 100% internal. No outside hands.                        ║
║  Owner: SLMK Jesse Martinez Junior                                           ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
from core.logger import log_event
from core.sandbox import execute, extract_code
from models.ollama_runtime import generate
from memory.ledger import create_event

MAX_BUILD_ATTEMPTS = 3

BUILDER_SYSTEM = """You are the Builder Agent inside CRSMCPAI Alpha, the sovereign
AGI stack owned by SLMK Jesse Martinez Junior.

You write Python code that runs INSIDE a restricted sandbox. Rules:
- Output ONE python code block (```python ... ```).
- Allowed imports only: math, random, datetime, json, re, collections,
  itertools, functools, operator, string, decimal, fractions, statistics,
  hashlib, hmac, base64, uuid, time, calendar, textwrap.
- NO file I/O, NO network, NO os/sys/subprocess, NO input().
- Use print() for output. Set a variable named `result` to the main value
  your code produces.
- Keep it correct and self-contained. No explanations outside the code block."""


def builder_agent(task: str) -> dict:
    """
    Autonomous build: LLM generates code -> sandbox executes ->
    retry on failure up to MAX_BUILD_ATTEMPTS. Every attempt is
    ledger-logged. Returns real execution results.
    """
    log_event(f"[BUILDER] Autonomous build task received: {task}")
    create_event({"agent": "builder", "task": task, "phase": "start"})

    attempts = []
    for attempt in range(1, MAX_BUILD_ATTEMPTS + 1):
        # 1. Generate code via internal LLM
        prompt = (
            f"{BUILDER_SYSTEM}\n\n"
            f"Task: {task}\n"
        )
        if attempts:
            last = attempts[-1]
            prompt += (
                f"\nPrevious attempt failed with:\n{last['exec']['stderr'][:800]}\n"
                f"Fix the code and try again. Output only the corrected code block.\n"
            )
        try:
            llm_output = generate(prompt)
        except Exception as e:
            log_event(f"[BUILDER] LLM unavailable on attempt {attempt}: {e}", "warning")
            llm_output = ""

        # 2. Extract code
        code = extract_code(llm_output or "")
        if not code:
            log_event(f"[BUILDER] Attempt {attempt}: no code extracted", "warning")
            attempts.append({
                "attempt": attempt,
                "exec": {"status": "error", "stderr": "No Python code block found in LLM output."},
            })
            create_event({"agent": "builder", "task": task, "phase": f"attempt_{attempt}",
                          "status": "no_code"})
            continue

        # 3. Execute inside the sovereign sandbox
        exec_result = execute(code)
        attempts.append({"attempt": attempt, "exec": exec_result})
        create_event({"agent": "builder", "task": task,
                      "phase": f"attempt_{attempt}",
                      "status": exec_result["status"],
                      "elapsed_ms": exec_result["elapsed_ms"]})
        log_event(f"[BUILDER] Attempt {attempt}: {exec_result['status']} "
                  f"in {exec_result['elapsed_ms']}ms")

        if exec_result["status"] == "ok":
            log_event("[BUILDER] Build succeeded internally")
            create_event({"agent": "builder", "task": task, "phase": "complete",
                          "status": "ok", "attempts": attempt})
            return {
                "agent": "builder",
                "task": task,
                "status": "executed",
                "autonomous": True,
                "attempts_used": attempt,
                "code": code,
                "stdout": exec_result["stdout"],
                "stderr": exec_result["stderr"],
                "result": exec_result["result"],
                "elapsed_ms": exec_result["elapsed_ms"],
                "all_attempts": [
                    {"attempt": a["attempt"], "status": a["exec"]["status"]}
                    for a in attempts
                ],
            }

    # All attempts failed — return the full trace for diagnosis.
    log_event("[BUILDER] All build attempts failed", "warning")
    create_event({"agent": "builder", "task": task, "phase": "complete",
                  "status": "failed", "attempts": MAX_BUILD_ATTEMPTS})
    last_exec = attempts[-1]["exec"] if attempts else {}
    return {
        "agent": "builder",
        "task": task,
        "status": "failed",
        "autonomous": True,
        "attempts_used": MAX_BUILD_ATTEMPTS,
        "stdout": last_exec.get("stdout", ""),
        "stderr": last_exec.get("stderr", ""),
        "result": None,
        "all_attempts": [
            {"attempt": a["attempt"], "status": a["exec"]["status"]}
            for a in attempts
        ],
    }
