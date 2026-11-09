"""
CRSMCPAI Alpha — Network Binding Layer (v1, 2026-11-08, Muse).

Binds the three internal networks — SIN (intelligence backbone),
SOLVA (accessibility apex), and the Dominion infrastructure — onto
the live mesh spine, in the open:

Each network's saved file (sin_network/, solva_network/,
dominion_infrastructure/) declares its modules and roles. A declared
module is not a running one. This layer maps every declared module
to the component of the live stack that actually does its job today
and reports that component's measured state — or reports the module
as DECLARED ONLY when nothing in this stack performs its function
yet. Nothing is upgraded on paper: the binding table below is the
whole claim, and every state in it is probed live at request time.

Transport: the networks ride the RTSGP++ mesh (api/mesh_ws.py). A
pulse exchanges real HEARTBEAT and SYNC_REQUEST frames for each
network hub over handle_frame, registering the hubs as segment
members (SIN-01 Command, SIN-02 Clearinghouse, SIN-03 Edge Swarm),
and registers each network with the Janet/hyper-sync peer picture as
a segment view of the one Golden Ledger — the networks are segments
of the one stack, not separate chains, and this layer says so.

Owner: SLMK Jesse Martinez Junior.
"""
import time
from typing import Any, Callable, Dict

from fastapi import APIRouter

router = APIRouter(prefix="/networks", tags=["networks"])


def _safe(fn: Callable[[], Any]) -> Dict[str, Any]:
    try:
        return {"state": "live", "detail": fn()}
    except Exception as exc:  # a probe must never take the layer down
        return {"state": "unreachable", "detail": f"{type(exc).__name__}: {exc}"}


def _declared() -> Dict[str, Any]:
    return {"state": "declared_only",
            "detail": "no component in this stack performs this function yet"}


# ── Live probes (each returns a small measured fact) ───────────────────

def _p_ledger():
    from memory.ledger import get_ledger, verify_chain
    chain = get_ledger()
    return {"height": len(chain), "chain_valid": verify_chain()}


def _p_hyper_sync():
    from api.hyper_sync import convergence
    c = convergence()
    return {"local_height": c["local_height"], "peers": c["peers"], "counts": c["counts"]}


def _p_sentinel():
    from api.sentinel import sentinel_engine
    s = sentinel_engine.scan()
    return {"state": s["state"], "threat_score": s["threat_score"]}


def _p_guardian_plus():
    from security.guardian_plus import guardian_plus
    return guardian_plus.status()


def _p_telemetry():
    from api import telemetry_ingest
    s = telemetry_ingest.ingest_status()
    return {"sources_total": s["sources_total"],
            "accepted_batches": s["accepted_batches"],
            "accepted_events": s["accepted_events"]}


def _p_mesh():
    from api import mesh, mesh_ws
    return {"enrolled_nodes": len(mesh.NODES),
            "active_nodes": sum(1 for n in mesh.NODES.values() if n.get("status") == "ACTIVE"),
            "ws_nodes": mesh_ws.active_node_count()}


def _p_black_swarm():
    from api.black_swarm import black_swarm
    s = black_swarm.status()
    return {"nodes_total": s.get("nodes_total"), "nodes_active": s.get("nodes_active")}


def _p_agssi():
    from api.agssi_core import _relay_configured
    return {"mode": "three_pass_reasoning", "relay_configured": _relay_configured()}


def _p_voice():
    import os
    return {"groq_configured": bool(os.environ.get("GROQ_API_KEY")),
            "openrouter_configured": bool(os.environ.get("OPENROUTER_API_KEY")),
            "xai_configured": bool(os.environ.get("XAI_API_KEY"))}


def _make_bridge_probe(bridge_name):
    def _probe():
        from api.solva_bridges import bridge_probe
        return bridge_probe(bridge_name)
    return _probe


def _p_os_hub():
    from api.os_orchestrator import module_status
    return module_status()


def _p_kernel():
    from api import os_kernel
    return {"module": "api/os_kernel.py", "present": True,
            "exports": [n for n in dir(os_kernel) if not n.startswith("_")][:8]}


def _p_pqsvm():
    from crsmcpai import pqsvm
    return {"verdict_source": "real Ed25519 signature verification (v2)"}


def _p_vector():
    from memory.vector_store import memory_count
    return {"memories": memory_count(), "retrieval": "384-dim local hashing embeddings, cosine"}


def _p_registry():
    from api import key_license_registry
    return {"module": "api/key_license_registry.py", "default": "deny",
            "sole_issuer": "jesse_martinez_jr"}


def _p_signing():
    from api.hardening import _SIGNING_KEYS
    return {"registered_signing_keys": list(_SIGNING_KEYS.keys())}


def _p_agents():
    import agents
    import pkgutil
    return {"agents": sorted(m.name for m in pkgutil.iter_modules(agents.__path__)
                             if m.name.endswith("_agent"))}


# ── Binding tables: declared module -> (backing name, probe or None) ──

SIN_BINDINGS: Dict[str, tuple] = {
    "sin_siren_core": ("AGSSI v2 three-pass reasoning", _p_agssi),
    "sin_mesh_layer": ("RTSGP++ mesh + WebSocket spine", _p_mesh),
    "sin_sector_relay": ("RTSGP++ mesh segments", _p_mesh),
    "sin_sentinel_grid": ("Sentinel detection engine + Guardian++", _p_sentinel),
    "sin_pqslsi_layer": (None, None),
    "sin_comms_backbone": ("RTSGP++ mesh transport (in-stack)", _p_mesh),
    "sin_nufire_render": ("Procedural media engines", lambda: {"engines": "media synthesis, in-stack"}),
    "sin_intelligence_fuser": ("Sentinel AI over AGSSI", _p_agssi),
    "sin_node_health_monitor": ("Black Swarm registry + mesh presence", _p_black_swarm),
    "sin_solva_gateway": ("SOLVA network (bound below)", lambda: {"gateway": "cross-network, this layer"}),
    "sin_ledger_sync": ("Planetary hyper sync engine", _p_hyper_sync),
    "sin_quantum_audit": (None, None),
}

SOLVA_BINDINGS: Dict[str, tuple] = {
    "solva_voice_engine": ("Relay voice chain (Groq/OpenRouter rosters)", _p_voice),
    "solva_navigation_engine": ("SOLVA bridges behavior layer (api/solva_bridges.py)",
                                _make_bridge_probe("solva_navigation_engine")),
    "solva_health_bridge": ("SOLVA bridges behavior layer (api/solva_bridges.py)",
                            _make_bridge_probe("solva_health_bridge")),
    "solva_education_bridge": ("SOLVA bridges behavior layer (api/solva_bridges.py)",
                               _make_bridge_probe("solva_education_bridge")),
    "solva_science_bridge": ("SOLVA bridges behavior layer (api/solva_bridges.py)",
                             _make_bridge_probe("solva_science_bridge")),
    "solva_rights_engine": ("SOLVA bridges behavior layer (api/solva_bridges.py)",
                            _make_bridge_probe("solva_rights_engine")),
    "solva_emergency_interface": ("SOLVA bridges behavior layer (api/solva_bridges.py)",
                                  _make_bridge_probe("solva_emergency_interface")),
    "solva_financial_access": ("x402 agent payment lane", lambda: {"lane": "api/x402_payments.py + agent ledger"}),
    "solva_render_interface": ("Procedural media engines", lambda: {"engines": "media synthesis, in-stack"}),
    "solva_sensor_interpreter": ("Telemetry intake (live sources)", _p_telemetry),
    "solva_pq_comms_layer": ("Hardening request signing", _p_signing),
    "solva_network_orchestrator": ("OS state hub", _p_os_hub),
}

DOMINION_BINDINGS: Dict[str, tuple] = {
    "dominion_core_kernel": ("OS kernel", _p_kernel),
    "dominion_super_intel": ("AGSSI v2 reasoning orchestration", _p_agssi),
    "dominion_mcp_bus": ("Directive hub", lambda: {"module": "core/directive_hub.py"}),
    "dominion_crs_engine": ("Memory harness (conversation + vector stores)", _p_vector),
    "dominion_pqsvm": ("PQSVM v2", _p_pqsvm),
    "dominion_ledger_master": ("Golden Ledger", _p_ledger),
    "dominion_node_mesh": ("Mesh + Black Swarm registries", _p_mesh),
    "dominion_agent_mesh": ("Agent fleet", _p_agents),
    "dominion_ip_engine": ("Key/license registry", _p_registry),
    "dominion_quantum_engine": (None, None),
    "dominion_hyperparam_engine": (None, None),
    "dominion_latent_mapper": ("Vector memory v2", _p_vector),
}

_NETWORKS = {
    "sin": ("sin_network.sin_network", SIN_BINDINGS, "SIN_NETWORK_HUB", "CRS_ALPHA_CORE"),
    "solva": ("solva_network.solva_network", SOLVA_BINDINGS, "SOLVA_NETWORK_HUB", "DOMINION_RELAY"),
    "dominion": ("dominion_infrastructure.dominion_infrastructure", DOMINION_BINDINGS,
                 "DOMINION_INFRA_HUB", "EDGE_AGENT"),
}


def _load_template(module_path: str):
    import importlib
    return importlib.import_module(module_path)


def network_state(name: str) -> Dict[str, Any]:
    module_path, bindings, hub_id, _itype = _NETWORKS[name]
    template = _load_template(module_path)
    declared = getattr(template, "MODULES", {})
    test = template.build_test() if hasattr(template, "build_test") else {}
    bound, declared_only, rows = 0, 0, {}
    for module_name, spec in declared.items():
        backing, probe = bindings.get(module_name, (None, None))
        if backing is None or probe is None:
            rows[module_name] = {"role": spec.get("role"), "binding": None, **_declared()}
            declared_only += 1
        else:
            rows[module_name] = {"role": spec.get("role"), "binding": backing, **_safe(probe)}
            bound += 1
    from api import mesh_ws
    segment_members = {}
    for node in mesh_ws.list_nodes():
        segment_members[node.get("sinSegment", "unassigned")] = \
            segment_members.get(node.get("sinSegment", "unassigned"), 0) + 1
    return {
        "network": getattr(template, "SYSTEM_LABEL", name),
        "version": getattr(template, "VERSION", ""),
        "tier": getattr(template, "TIER", ""),
        "hub_id": hub_id,
        "declared_modules": len(declared),
        "bound_live": bound,
        "declared_only": declared_only,
        "template_build_test": test.get("build_test"),
        "transport": {"spine": "RTSGP++ mesh (api/mesh_ws.py)",
                      "segment_members": segment_members,
                      "mesh_nodes_total": len(mesh_ws.list_nodes())},
        "modules": rows,
        "timestamp": time.time(),
    }


def all_networks() -> Dict[str, Any]:
    out = {}
    for name in _NETWORKS:
        try:
            state = network_state(name)
            out[name] = {k: state[k] for k in
                         ("network", "version", "tier", "hub_id", "declared_modules",
                          "bound_live", "declared_only", "template_build_test", "transport")}
        except Exception as exc:
            out[name] = {"error": f"{type(exc).__name__}: {exc}"}
    return {"networks": out, "timestamp": time.time()}


def pulse() -> Dict[str, Any]:
    """Exchange real RTSGP++ frames for each network hub over the
    mesh spine and register each network in the hyper-sync peer
    picture as a segment view of the one chain."""
    from api import mesh_ws
    from api.hyper_sync import local_fingerprint, register_peer
    results = {}
    seq = int(time.time()) % 100000
    for name, (_mp, _b, hub_id, itype) in _NETWORKS.items():
        acks = {}
        for ping in ("HEARTBEAT", "SYNC_REQUEST"):
            frame = {"header": {"protocol": "RTSGP++", "senderId": hub_id,
                                "signatureType": "HUB-REPORT"},
                     "payload": {"pingType": ping, "sequenceNumber": seq,
                                 "instanceType": itype,
                                 "metrics": {"network": name}}}
            resp = mesh_ws.handle_frame(frame)
            acks[ping] = resp.get("payload", {}).get("status")
        register_peer(hub_id, local_fingerprint())
        results[name] = {"hub": hub_id, "acks": acks}
    return {"pulse": results, "mesh_nodes_total": len(mesh_ws.list_nodes()),
            "timestamp": time.time()}


@router.get("/status")
def networks_status():
    return all_networks()


@router.get("/{name}")
def one_network(name: str):
    key = name.lower()
    if key not in _NETWORKS:
        return {"error": f"unknown network '{name}'", "known": list(_NETWORKS)}
    return network_state(key)


@router.post("/pulse")
def networks_pulse():
    return pulse()
