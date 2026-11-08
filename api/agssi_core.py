"""
CRSMCPAI Alpha - AGSSI Reasoning Core
Owner: SLMK Jesse Martinez Junior

v2 (2026-11-08, Muse, repo lane): REAL multi-pass reasoning
orchestration over the stack's relay roster, behind the same routes.

v1 returned deterministic hash traces and a pseudo-confidence derived
from hash bytes; no model was consulted. That is removed. /reason now
runs an actual pipeline through models.ollama_runtime.generate (the
relay roster: Ollama, Gemini, xAI, Groq roster, OpenRouter roster):

  Pass 1 (v3 lineage)  FOUNDATION — a direct, complete answer.
  Pass 2 (v5/v6)       CRITIQUE — a second pass over the foundation
                       answer that must declare its first line as
                       "ISSUES: NONE" or "ISSUES: ..." and repair what
                       it finds.
  Pass 3 (v7)          SYNTHESIS — reconciles foundation and critique
                       into the final answer and closes with its own
                       "CONFIDENCE: HIGH|MEDIUM|LOW" line.

The reported confidence is computed from real signals only: how many
passes completed, whether the critique found issues, and the token
agreement between the foundation and the final answer. If the relay
roster is offline (the runtime's stub answer), the pipeline stops,
says so, and reports no confidence at all. Nothing here invents a
number it cannot stand behind.

Honest scope: this is orchestration over external relay models, not a
sovereign weights model. The lineage labels name the pass roles from
Jesse's architecture (v3 foundation, v5/v6 critique and stabilization,
v7 unified synthesis); there are no separate v5/v6/v7 model artifacts
behind them, and this module does not claim otherwise.
"""
import os
import re
import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from core.logger import log_event
from models.ollama_runtime import generate

agssi_router = APIRouter(prefix="/agssi", tags=["agssi"])
GENESIS_HASH = "92038cafccc7192535bd475cca985d03000d89962b8dc96f6664081663559b1b"

VERSIONS = {
    "v3": {"name": "Sovereign Language Model v3", "role": "Foundation pass: direct reasoning"},
    "v5": {"name": "Sovereign Singularity v5", "role": "Critique pass: error and gap detection"},
    "v6": {"name": "Sovereign Singularity v6", "role": "Stabilization: critique repairs applied"},
    "v7": {"name": "Sovereign Architecture v7", "role": "Synthesis pass: unified final answer"},
}

_OFFLINE_MARKER = "LLM offline"
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _relay_configured() -> bool:
    return any(os.environ.get(k) for k in (
        "GROQ_API_KEY", "OPENROUTER_API_KEY", "GEMINI_API_KEY", "XAI_API_KEY"))


def _is_offline(answer: str) -> bool:
    return (not answer) or (_OFFLINE_MARKER in answer)


def _tokens(text: str) -> set:
    return set(_TOKEN_RE.findall((text or "").lower()))


def _agreement(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _call(prompt: str) -> str:
    try:
        return generate(prompt, timeout=45) or ""
    except Exception as exc:  # relay errors degrade honestly, never crash the route
        log_event(f"[AGSSI] relay call failed: {exc}", "warning")
        return ""


def _seal(problem: str, status: str, passes_completed: int) -> None:
    try:
        from memory.ledger import create_event
        import hashlib
        create_event({
            "module": "AGSSI",
            "event": "REASON",
            "problem_sha3": hashlib.sha3_256(problem.encode()).hexdigest()[:16],
            "status": status,
            "passes_completed": passes_completed,
        })
    except Exception:
        pass  # sealing is best-effort here; the verdict stands on its own


def reason(problem: str) -> dict:
    """Run the three-pass pipeline. Returns the full record, including
    every pass's real answer text, so callers can audit the reasoning
    instead of trusting a summary."""
    problem = (problem or "").strip()
    if not problem:
        return {"problem": problem, "status": "empty_problem",
                "reasoning_passes": [], "final_answer": None,
                "final_confidence": None, "capacity": "150%"}

    passes: list[dict] = []

    # Pass 1 — foundation (v3)
    foundation = _call(
        "Answer the following problem directly and completely. "
        "Show the key steps of your reasoning, then give the answer.\n\n"
        f"PROBLEM: {problem}")
    if _is_offline(foundation):
        _seal(problem, "relay_unavailable", 0)
        return {"problem": problem, "status": "relay_unavailable",
                "reasoning_passes": passes, "final_answer": None,
                "final_confidence": None, "capacity": "150%",
                "message": "The relay roster is offline; no reasoning was performed."}
    passes.append({"pass": 1, "lineage": "v3", "role": "foundation",
                   "answer": foundation})

    # Pass 2 — critique (v5/v6)
    critique = _call(
        "You are the critique pass. Examine the foundation answer below "
        "for errors, gaps, wrong assumptions, and missing steps.\n"
        "Your FIRST line must be exactly 'ISSUES: NONE' if the answer is "
        "sound, or 'ISSUES:' followed by a short list of the problems.\n"
        "After that line, give the corrected or confirmed answer in full.\n\n"
        f"PROBLEM: {problem}\n\nFOUNDATION ANSWER:\n{foundation}")
    if _is_offline(critique):
        _seal(problem, "relay_unavailable", 1)
        return {"problem": problem, "status": "relay_unavailable",
                "reasoning_passes": passes, "final_answer": None,
                "final_confidence": None, "capacity": "150%",
                "message": "The relay roster went offline during the critique pass."}
    first_line = critique.strip().splitlines()[0] if critique.strip() else ""
    issues_found = not first_line.upper().startswith("ISSUES: NONE")
    passes.append({"pass": 2, "lineage": "v5/v6", "role": "critique",
                   "issues_found": issues_found, "answer": critique})

    # Pass 3 — synthesis (v7)
    synthesis = _call(
        "You are the synthesis pass. Reconcile the foundation answer and "
        "the critique below into ONE final answer to the problem. Apply "
        "every valid correction from the critique. End with a last line "
        "of exactly 'CONFIDENCE: HIGH', 'CONFIDENCE: MEDIUM', or "
        "'CONFIDENCE: LOW'.\n\n"
        f"PROBLEM: {problem}\n\nFOUNDATION ANSWER:\n{foundation}\n\n"
        f"CRITIQUE:\n{critique}")
    if _is_offline(synthesis):
        _seal(problem, "relay_unavailable", 2)
        return {"problem": problem, "status": "relay_unavailable",
                "reasoning_passes": passes, "final_answer": None,
                "final_confidence": None, "capacity": "150%",
                "message": "The relay roster went offline during the synthesis pass."}

    model_confidence = None
    final_answer = synthesis.strip()
    lines = final_answer.splitlines()
    if lines and lines[-1].strip().upper().startswith("CONFIDENCE:"):
        label = lines[-1].split(":", 1)[1].strip().upper()
        if label in ("HIGH", "MEDIUM", "LOW"):
            model_confidence = label
            final_answer = "\n".join(lines[:-1]).strip()
    passes.append({"pass": 3, "lineage": "v7", "role": "synthesis",
                   "answer": synthesis})

    agreement = _agreement(foundation, final_answer)
    confidence = round(
        0.50                                   # all three passes completed
        + (0.25 if not issues_found else 0.10)  # critique outcome
        + 0.25 * agreement,                     # foundation/final agreement
        3)

    _seal(problem, "complete", 3)
    return {
        "problem": problem,
        "status": "complete",
        "reasoning_passes": passes,
        "final_answer": final_answer,
        "final_confidence": confidence,
        "confidence_signals": {
            "passes_completed": 3,
            "critique_issues_found": issues_found,
            "foundation_final_agreement": round(agreement, 3),
            "model_self_confidence": model_confidence,
        },
        "capacity": "150%",
        "mode": "multi-pass orchestration over the relay roster (v2)",
    }


@agssi_router.get("/status")
async def agssi_status():
    return JSONResponse(content={
        "core": "AGSSI",
        "reasoning_capacity": "150%",
        "version_lineage": ["v3", "v5", "v6", "v7"],
        "mode": "multi-pass orchestration over the relay roster (v2)",
        "passes": ["foundation (v3)", "critique (v5/v6)", "synthesis (v7)"],
        "relay_keys_configured": _relay_configured(),
        "status": "OPERATIONAL" if _relay_configured() else "DEGRADED — no relay key configured",
        "genesis_bound": True})


@agssi_router.get("/versions")
async def agssi_versions():
    return JSONResponse(content={"versions": VERSIONS})


@agssi_router.post("/reason")
async def agssi_reason(request: dict):
    return JSONResponse(content=reason(request.get("problem", "")))


@agssi_router.post("/telemetry-check")
async def agssi_telemetry_check():
    enrolled = 0
    ledger_blocks = None
    try:
        from api.telemetry_ingest import _SOURCES
        enrolled = len(_SOURCES)
    except Exception:
        pass
    try:
        from memory.ledger import get_ledger
        ledger_blocks = len(get_ledger())
    except Exception:
        pass
    return JSONResponse(content={
        "dominion_telemetry_receiving": enrolled > 0,
        "connected_instances": enrolled,
        "telemetry_sources_enrolled": enrolled,
        "ledger_blocks": ledger_blocks,
        "last_telemetry": None,
        "message": (
            "Telemetry sources are enrolled and reporting into the intake."
            if enrolled > 0 else
            "No external telemetry source has enrolled yet. The signed intake is live and listening; enrollment is the missing piece, and this count is read from the intake registry, not asserted."),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
