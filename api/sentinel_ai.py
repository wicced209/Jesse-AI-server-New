"""
CRSMCPAI Alpha — Sentinel AI (v1, 2026-11-08, Muse).

The reasoning layer over the Sentinel detection engine, built from
the recovered spec (Sentinel AI sat at EXISTENCE UNCONFIRMED — a
capability description, no code). From that description, the parts
that can be built for real today:

  1. OMNI-OBSERVATION SUMMARY — one computed view over the watch
     layer: the Sentinel engine's scan, its recent alerts, and the
     Black Swarm's mesh state.
  2. LEDGER INTEGRITY VERIFICATION — the spec's "continuous
     integrity verification of all sovereign ledgers": runs the real
     hash-chain verification (memory.ledger.verify_chain) and reports
     the verdict and block count. A broken chain raises a Sentinel
     alert through the engine.
  3. ASSESSMENT — hands the current alert picture to the AGSSI
     multi-pass reasoner and returns its verdict verbatim, with its
     computed confidence. If the relay roster is offline, the AGSSI
     result says relay_unavailable and this layer passes that through
     untouched — no invented assessment.

Sentinel AI observes, verifies, and assesses. It does not execute
responses; defensive coordination belongs to the Black Swarm under
the owner's authority.
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from core.logger import log_event

sentinel_ai_router = APIRouter(prefix="/sentinel-ai", tags=["sentinel-ai"])


def observe() -> dict:
    from api.sentinel import sentinel_engine
    out = {"scan": sentinel_engine.scan(), "recent_alerts": sentinel_engine.alerts(10)}
    try:
        from api.black_swarm import black_swarm
        out["swarm"] = black_swarm.status()
    except Exception:
        out["swarm"] = None
    return out


def verify_ledgers() -> dict:
    result = {"ledgers": {}}
    try:
        from memory.ledger import get_ledger, verify_chain
        chain_ok = bool(verify_chain())
        result["ledgers"]["golden_ledger"] = {
            "blocks": len(get_ledger()), "chain_valid": chain_ok}
        if not chain_ok:
            from api.sentinel import sentinel_engine
            sentinel_engine.ingest({
                "source": "sentinel-ai", "kind": "integrity", "ok": False,
                "action": "LEDGER_CHAIN_INVALID"})
            log_event("[SENTINEL AI] golden ledger chain verification FAILED", "warning")
    except Exception as exc:
        result["ledgers"]["golden_ledger"] = {"error": str(exc)}
    result["all_valid"] = all(
        v.get("chain_valid") for v in result["ledgers"].values() if "chain_valid" in v)
    return result


def assess() -> dict:
    from api.agssi_core import reason
    from api.sentinel import sentinel_engine
    scan = sentinel_engine.scan()
    alerts = sentinel_engine.alerts(10)
    if not alerts:
        return {"assessment": None, "status": "no_alerts",
                "message": "No alerts to assess. The watch layer is quiet."}
    picture = (
        f"Sentinel scan: state {scan['state']}, threat score {scan['threat_score']}, "
        f"{scan['alerts_active']} active alerts, {scan['events_seen']} events seen.\n"
        "Recent alerts:\n" + "\n".join(
            f"- {a['rule']} ({a['severity']}) from source {a['source']}: {a['detail']}"
            for a in alerts))
    verdict = reason(
        "You are Sentinel AI assessing the watch layer of a sovereign system. "
        "Given the detection picture below, state in plain sentences: what is "
        "happening, how serious it is, and what the operator should do next.\n\n"
        + picture)
    return {"assessment": verdict, "status": verdict.get("status"),
            "picture": picture}


@sentinel_ai_router.get("/observe")
async def sentinel_ai_observe():
    return JSONResponse(content=observe())


@sentinel_ai_router.get("/verify-ledgers")
async def sentinel_ai_verify():
    return JSONResponse(content=verify_ledgers())


@sentinel_ai_router.post("/assess")
async def sentinel_ai_assess():
    return JSONResponse(content=assess())
