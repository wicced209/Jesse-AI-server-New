from core.logger import log_event
from security.crypto import sign_data
from security.auth import authenticate
from crsmcpai.pqsvm import pqsvm_verify


def guardian_agent(task: str, user: str = "admin") -> dict:
    """
    Security / verification agent.
    - Authenticates the requesting user
    - Signs the task payload
    - Runs PQSVM post-quantum verification
    """
    log_event(f"[GUARDIAN] Task received: {task} | User: {user}")

    # ── Step 1: Authenticate user ──────────────────────────────────────────
    if not authenticate(user):
        log_event(f"[GUARDIAN] Authentication FAILED for user: {user}", "warning")
        return {
            "agent":  "guardian",
            "task":   task,
            "status": "auth_failed",
            "reason": f"User '{user}' is not authorized",
        }

    # ── Step 2: Sign payload ───────────────────────────────────────────────
    payload_bytes = task.encode("utf-8")
    signature     = sign_data(payload_bytes)
    log_event(f"[GUARDIAN] Payload signed: {signature[:16]}...")

    # ── Step 3: PQSVM verification ─────────────────────────────────────────
    pqsvm_result = pqsvm_verify(task, signature)
    log_event(f"[GUARDIAN] PQSVM result: {pqsvm_result}")

    return {
        "agent":       "guardian",
        "task":        task,
        "user":        user,
        "signature":   signature[:32] + "...",   # truncate for display
        "pqsvm":       pqsvm_result,
        "status":      "verified",
    }
