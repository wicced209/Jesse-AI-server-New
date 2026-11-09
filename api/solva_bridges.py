"""SOLVA network bridges — behavior layer (2026-11-09, Muse).

The SOLVA network template (solva_network/solva_network.py) declares
twelve modules. Six of them had no component in the live stack
performing their function, and api/networks.py reported them as
DECLARED ONLY:

  solva_navigation_engine    real-time audio wayfinding / routing
  solva_health_bridge        voice-accessible health intelligence
  solva_education_bridge     audio-first adaptive learning
  solva_science_bridge       accessible research interface
  solva_rights_engine        disability rights / legal advisory
  solva_emergency_interface  accessible emergency response

This module gives each of those six a real duty performed against
live stack components that exist today, and says plainly where the
original sector scope does NOT exist in this stack:

  navigation  An in-stack routing plan: a named target (a network,
              an OS, a SOLVA family module, a kernel surface, or an
              MCP handler) is resolved against the live registries
              and the hop-by-hop path is returned with each hop's
              live/bound state probed at request time. There is NO
              maps / GPS / transport component in this stack, so no
              geographic or real-world directions are produced, and
              the result says so.
  health      A live health picture of the stack itself, probed
              component by component (ledger chain, Sentinel,
              telemetry intake, vector memory, mesh, OS family),
              with a computed overall state. There is NO medical
              sector in this stack: a medical question is answered
              with an honest not-integrated report, never advice.
  education   A grounded answer path: the question is retrieved
              against vector memory and the CRS working window, then
              run through the AGSSI three-pass pipeline. When the
              relay roster is offline the AGSSI verdict is
              relay_unavailable and the answer is None — the
              retrieved grounding is still returned, nothing is
              invented.
  science     The same grounded path, reported as a research
              result: retrieved sources with their cosine scores,
              the CRS assembly, and the AGSSI verdict.
  rights      Guardian++ and the key/license registry: registry
              state is read live, and when a user and action are
              supplied a real Guardian++ verdict is computed for
              them (owner override, restricted actions, velocity).
  emergency   The Sentinel watch: a fresh scan, the active
              alerts, the Black Swarm registry, and telemetry state,
              combined into a computed escalation level. When an
              event is supplied it is really ingested into the
              Sentinel engine and any alerts it raises are returned.

Every duty returns its errors as an {"error": ...} result and never
raises, following the SOLVA family behavior-edition pattern.

Routes (wired in api/server.py the way api/hud.py is wired):
  GET  /solva-bridges/status
  GET  /solva-bridges/{name}
  POST /solva-bridges/{name}/operate   JSON body = the duty payload

Owner: SLMK Jesse Martinez Junior.
"""
import time
from typing import Any, Dict

from fastapi import APIRouter
from fastapi.responses import JSONResponse

solva_bridges_router = APIRouter(prefix="/solva-bridges", tags=["solva-bridges"])


# ── Duties ─────────────────────────────────────────────────────────────

def _duty_navigation(payload: Dict[str, Any]) -> Dict[str, Any]:
    target = str(payload.get("target") or payload.get("destination") or "").strip()
    from api.networks import all_networks
    nets = all_networks()["networks"]
    hops = [{"hop": "user", "state": "live"},
            {"hop": "solva_network_hub", "state": "live",
             "detail": {"bound_live": nets.get("solva", {}).get("bound_live"),
                        "declared_modules": nets.get("solva", {}).get("declared_modules")}}]
    found = False
    kind = None
    if target:
        low = target.lower()
        if low in nets:
            kind, found = "network", True
            row = nets[low]
            hops.append({"hop": target, "state": "live",
                         "detail": {"bound_live": row.get("bound_live"),
                                    "declared_only": row.get("declared_only")}})
        else:
            try:
                from solva_modules.family import SOLVA_MODULES
                for mod in SOLVA_MODULES.values():
                    if low in (mod.module_id, mod.name.lower()):
                        kind, found = "solva_family_module", True
                        hops.append({"hop": mod.module_id, "state": "live",
                                     "detail": mod.status()})
                        break
            except Exception:
                pass
        if not found:
            try:
                from crsmcpai.module_context_protocol import mcp
                if low in [h.lower() for h in mcp.list_handlers()]:
                    kind, found = "mcp_handler", True
                    hops.append({"hop": target, "state": "live",
                                 "detail": {"handlers": sorted(mcp.list_handlers())}})
            except Exception:
                pass
        if not found:
            try:
                from api.os_family import family_status
                fam = family_status()["family"]
                if low in fam:
                    kind, found = "os_family", True
                    hops.append({"hop": target, "state": "live",
                                 "detail": {"last_passed": fam[low].get("last_passed"),
                                            "lifecycle": fam[low].get("lifecycle")}})
            except Exception:
                pass
    return {
        "target": target or None,
        "found": found,
        "target_kind": kind,
        "route": hops,
        "reachable": found,
        "scope": "in-stack routing plan only — this stack has no maps, GPS, "
                 "or transport component, so no geographic directions are produced",
    }


def _duty_health(payload: Dict[str, Any]) -> Dict[str, Any]:
    if payload.get("symptom") or payload.get("medical_query") or payload.get("medical"):
        return {"integrated": False, "domain": "medical",
                "reason": "no medical sector or clinical component exists in this "
                          "stack; medical advice is not produced. This bridge "
                          "reports the live health of the stack itself."}
    components: Dict[str, Any] = {}
    try:
        from memory.ledger import get_ledger, verify_chain
        components["ledger"] = {"height": len(get_ledger()), "chain_valid": verify_chain()}
    except Exception as exc:
        components["ledger"] = {"error": f"{type(exc).__name__}: {exc}"}
    try:
        from api.sentinel import sentinel_engine
        s = sentinel_engine.scan()
        components["sentinel"] = {"state": s["state"], "threat_score": s["threat_score"],
                                  "alerts_active": s["alerts_active"]}
    except Exception as exc:
        components["sentinel"] = {"error": f"{type(exc).__name__}: {exc}"}
    try:
        from api.telemetry_ingest import ingest_status
        t = ingest_status()
        components["telemetry"] = {"sources_total": t["sources_total"],
                                   "accepted_events": t["accepted_events"]}
    except Exception as exc:
        components["telemetry"] = {"error": f"{type(exc).__name__}: {exc}"}
    try:
        from memory.vector_store import memory_count
        components["vector_memory"] = {"memories": memory_count()}
    except Exception as exc:
        components["vector_memory"] = {"error": f"{type(exc).__name__}: {exc}"}
    try:
        from api import mesh
        components["mesh"] = {"enrolled_nodes": len(mesh.NODES),
                              "active_nodes": sum(1 for n in mesh.NODES.values()
                                                  if n.get("status") == "ACTIVE")}
    except Exception as exc:
        components["mesh"] = {"error": f"{type(exc).__name__}: {exc}"}
    errors = [k for k, v in components.items() if "error" in v]
    chain_ok = components.get("ledger", {}).get("chain_valid") is True
    sentinel_ok = components.get("sentinel", {}).get("state") in ("NOMINAL", "ELEVATED")
    overall = "healthy" if (chain_ok and sentinel_ok and not errors) else "degraded"
    return {"overall": overall, "components": components,
            "components_errored": errors,
            "scope": "live health of the stack itself; no medical sector exists in this stack"}


def _grounded(payload: Dict[str, Any], domain: str) -> Dict[str, Any]:
    question = str(payload.get("question") or payload.get("query")
                   or payload.get("topic") or "").strip()
    if not question:
        return {"error": "empty_question: supply 'question', 'query', or 'topic'"}
    hits = []
    try:
        from memory.vector_store import search_memory
        hits = search_memory(question, top_k=5)
    except Exception as exc:
        hits = [{"error": f"{type(exc).__name__}: {exc}"}]
    assembled = None
    try:
        from crsmcpai.context_reasoning import crs
        assembled = crs.assemble(question)
    except Exception as exc:
        assembled = {"error": f"{type(exc).__name__}: {exc}"}
    verdict = None
    try:
        from api.agssi_core import reason as agssi_reason
        verdict = agssi_reason(question)
    except Exception as exc:
        verdict = {"status": "error", "detail": f"{type(exc).__name__}: {exc}"}
    status = (verdict or {}).get("status")
    return {"domain": domain, "question": question,
            "grounded_hits": hits, "crs_assembled": assembled,
            "agssi_status": status, "agssi": verdict,
            "answer": (verdict or {}).get("final_answer") if status == "complete" else None,
            "note": None if status == "complete" else
                    "no answer is invented when the reasoning relay is unavailable; "
                    "the retrieved grounding above is the real result"}


def _duty_education(payload: Dict[str, Any]) -> Dict[str, Any]:
    out = _grounded(payload, "education")
    if "grounded_hits" in out:
        out["reading_order"] = [h.get("text", h) if isinstance(h, dict) else h
                                for h in out["grounded_hits"]]
    return out


def _duty_science(payload: Dict[str, Any]) -> Dict[str, Any]:
    out = _grounded(payload, "science")
    if "grounded_hits" in out:
        out["sources"] = out["grounded_hits"]
    return out


def _duty_rights(payload: Dict[str, Any]) -> Dict[str, Any]:
    from api.key_license_registry import registry_status
    out: Dict[str, Any] = {"registry": registry_status()}
    try:
        from security.guardian_plus import guardian_plus
        out["guardian_plus"] = guardian_plus.status()
        user = str(payload.get("user") or "").strip()
        action = str(payload.get("action") or "").strip()
        if user and action:
            out["verdict"] = guardian_plus.validate(
                user, action, payload=str(payload.get("payload") or ""),
                source="solva-rights-engine")
    except Exception as exc:
        out["guardian_plus"] = {"error": f"{type(exc).__name__}: {exc}"}
    return out


def _duty_emergency(payload: Dict[str, Any]) -> Dict[str, Any]:
    from api.sentinel import sentinel_engine
    raised = None
    event = payload.get("event")
    if isinstance(event, dict) and event:
        raised = sentinel_engine.ingest(event)
    scan = sentinel_engine.scan()
    score = scan["threat_score"]
    level = ("none" if score == 0 else "watch" if score < 30
             else "urgent" if score < 70 else "critical")
    out: Dict[str, Any] = {"scan": scan, "alerts": sentinel_engine.alerts(limit=20),
                           "escalation_level": level, "raised_by_event": raised}
    try:
        from api.black_swarm import black_swarm
        out["black_swarm"] = black_swarm.status()
    except Exception as exc:
        out["black_swarm"] = {"error": f"{type(exc).__name__}: {exc}"}
    try:
        from api.telemetry_ingest import ingest_status
        out["telemetry"] = ingest_status()
    except Exception as exc:
        out["telemetry"] = {"error": f"{type(exc).__name__}: {exc}"}
    return out


_DUTIES = {
    "solva_navigation_engine": _duty_navigation,
    "solva_health_bridge": _duty_health,
    "solva_education_bridge": _duty_education,
    "solva_science_bridge": _duty_science,
    "solva_rights_engine": _duty_rights,
    "solva_emergency_interface": _duty_emergency,
}

_DESCRIPTIONS = {
    "solva_navigation_engine": "in-stack routing plan to a named live surface, probed at request time",
    "solva_health_bridge": "live component health probes of the stack, with a computed overall state",
    "solva_education_bridge": "grounded answer via vector memory + CRS assembly + AGSSI three-pass reasoning",
    "solva_science_bridge": "grounded research result via vector memory + CRS assembly + AGSSI three-pass reasoning",
    "solva_rights_engine": "Guardian++ verdicts and key/license registry state, read and computed live",
    "solva_emergency_interface": "Sentinel scan, active alerts, swarm and telemetry state, with a computed escalation level",
}

BRIDGE_NAMES = sorted(_DUTIES)


def operate_bridge(name: str, payload: Dict[str, Any] = None) -> Dict[str, Any]:
    payload = payload or {}
    duty = _DUTIES.get(name)
    if duty is None:
        return {"bridge": name, "error": f"unknown bridge '{name}'",
                "known": BRIDGE_NAMES}
    try:
        result = duty(payload)
    except Exception as exc:  # a duty must never take the layer down
        result = {"error": f"{type(exc).__name__}: {exc}"}
    return {"bridge": name, "duty": _DESCRIPTIONS[name],
            "result": result, "ts": time.time()}


def bridge_probe(name: str) -> Dict[str, Any]:
    """Small measured fact for api/networks.py binding, probed live.
    Deliberately cheap: no AGSSI reasoning call is made here."""
    if name == "solva_navigation_engine":
        # Cheap and non-recursive by design: this probe is CALLED by
        # api.networks.all_networks() (via _make_bridge_probe), so it
        # must never call all_networks() or anything that probes the
        # bridge layer — that was an unbounded recursion (each level
        # re-probed all six bridges, with mesh/ledger work per level).
        # Surfaces are the network names declared in the _NETWORKS
        # registry constant in api/networks.py, read without invoking
        # all_networks(); the two counts are len() over in-memory
        # registries whose accessors invoke no handlers and probe
        # nothing (verified: SOLVA_MODULES is a plain dict built at
        # import; mcp.list_handlers() only formats its registry dict).
        # The old "solva_bound_live" field is dropped: the only source
        # for it was all_networks() itself.
        from api.networks import _NETWORKS
        from crsmcpai.module_context_protocol import mcp
        from solva_modules.family import SOLVA_MODULES
        return {"surfaces": sorted(_NETWORKS),
                "network_count": len(_NETWORKS),
                "solva_family_modules": len(SOLVA_MODULES),
                "mcp_handlers": len(mcp.list_handlers())}
    if name == "solva_health_bridge":
        h = _duty_health({})
        return {"overall": h.get("overall"), "components": sorted(h.get("components", {}))}
    if name in ("solva_education_bridge", "solva_science_bridge"):
        from api.agssi_core import _relay_configured
        from memory.vector_store import memory_count
        return {"relay_configured": _relay_configured(), "vector_memories": memory_count()}
    if name == "solva_rights_engine":
        from api.key_license_registry import registry_status
        r = registry_status()
        return {"credentials_total": r["credentials_total"], "active": r["active"],
                "revoked": r["revoked"]}
    if name == "solva_emergency_interface":
        from api.sentinel import sentinel_engine
        s = sentinel_engine.scan()
        return {"state": s["state"], "threat_score": s["threat_score"],
                "alerts_active": s["alerts_active"]}
    return {"error": f"unknown bridge '{name}'"}


def bridges_status() -> Dict[str, Any]:
    out = {}
    for name in BRIDGE_NAMES:
        try:
            out[name] = {"state": "live", "duty": _DESCRIPTIONS[name],
                         "probe": bridge_probe(name)}
        except Exception as exc:
            out[name] = {"state": "unreachable",
                         "detail": f"{type(exc).__name__}: {exc}"}
    return {"bridges": out, "count": len(out), "timestamp": time.time()}


@solva_bridges_router.get("/status")
def solva_bridges_status():
    return bridges_status()


@solva_bridges_router.get("/{name}")
def solva_bridge_one(name: str):
    if name not in _DUTIES:
        return JSONResponse(status_code=404,
                            content={"error": f"unknown bridge '{name}'",
                                     "known": BRIDGE_NAMES})
    try:
        probe = bridge_probe(name)
        return {"bridge": name, "state": "live", "duty": _DESCRIPTIONS[name],
                "probe": probe}
    except Exception as exc:
        return {"bridge": name, "state": "unreachable",
                "detail": f"{type(exc).__name__}: {exc}"}


@solva_bridges_router.post("/{name}/operate")
def solva_bridge_operate(name: str, request: dict = None):
    # Accept either {"payload": {...}} or a bare duty payload object.
    body = request or {}
    payload = body.get("payload") if isinstance(body.get("payload"), dict) \
        and set(body) == {"payload"} else body
    return operate_bridge(name, payload)
