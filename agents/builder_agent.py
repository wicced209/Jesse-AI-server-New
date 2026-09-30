from core.logger import log_event
from models.ollama_runtime import generate
from memory.ledger import create_event


def builder_agent(task: str) -> dict:
    """
    Executes build/creation tasks using the local LLM.
    Records every build action to the immutable ledger.
    """
    log_event(f"[BUILDER] Task received: {task}")

    prompt = (
        f"You are Jesse AI's Builder Agent.\n"
        f"Execute and produce a result for: {task}\n"
        f"Be precise and return working output."
    )

    try:
        output = generate(prompt)
    except Exception as e:
        log_event(f"[BUILDER] LLM unavailable. Error: {e}", "warning")
        output = f"[Stub] Build output for: {task}"

    # Record build event to ledger
    create_event({"agent": "builder", "task": task})
    log_event(f"[BUILDER] Task executed and ledger updated")

    return {
        "agent":  "builder",
        "task":   task,
        "output": output,
        "status": "executed",
    }
