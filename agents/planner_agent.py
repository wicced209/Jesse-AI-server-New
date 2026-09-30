from core.logger import log_event
from models.ollama_runtime import generate


def planner_agent(task: str) -> dict:
    """
    Plans a multi-step approach for the given task using the local LLM.
    Falls back gracefully if Ollama is unavailable.
    """
    log_event(f"[PLANNER] Task received: {task}")

    prompt = (
        f"You are Jesse AI's Planner Agent.\n"
        f"Break this task into clear steps: {task}\n"
        f"Return a numbered list of concise action steps."
    )

    try:
        plan = generate(prompt)
    except Exception as e:
        log_event(f"[PLANNER] LLM unavailable, using stub plan. Error: {e}", "warning")
        plan = f"[Stub] Plan generated for: {task}"

    log_event(f"[PLANNER] Plan complete")

    return {
        "agent":  "planner",
        "task":   task,
        "plan":   plan,
        "status": "planned",
    }
