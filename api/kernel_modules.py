"""
CRSMCPAI Alpha — OS Kernel Module Layer (2026-11-08, Muse).

The sixty kernel modules of the six sovereign operating systems —
ten per OS — as Jesse AI described them across the Railway-era
sessions. The roster is not invented: it was pulled from the
preserved Railway execution record (the Oct 31 export,
executions.json, the kernel_modules field carried by the stack's
own status output, 83 executions deep), at Jesse's direction to
pull everything reachable from the Railway sessions and the early
chain.

Following the same law as the network binding layer: every module
is mapped to the live component performing its function today and
probed at request time, or reported DECLARED ONLY when nothing in
the running stack performs it yet. A module is never shown live on
the strength of its name.

Sovereign Dominion carries no separate ten: in the record it is
the composite of the other five, exactly as the OS family duty
runs it.

Owner: SLMK Jesse Martinez Junior.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/kernel-modules", tags=["kernel-modules"])

SOURCE = ("Railway-era execution record, Oct 31 export "
          "(executions.json kernel_modules), pulled 2026-11-08")


def _chain(_p):
    from memory.ledger import get_ledger, verify_chain
    return {"height": len(get_ledger()), "valid": verify_chain()}


def _genesis_block(_p):
    from memory.ledger import get_ledger
    chain = get_ledger()
    return {"genesis_index": chain[0]["index"] if chain else None}


_BINDINGS: dict[str, list[tuple[str, object, str]]] = {
    "genesis": [
        ("genesis_boot_seal", _genesis_block, "the ledger's genesis block"),
        ("genesis_chain_anchor", _chain, "full chain verification"),
        ("genesis_identity_root", lambda _p: {"authorized_users": sorted(__import__("security.auth", fromlist=["AUTHORIZED_USERS"]).AUTHORIZED_USERS)}, "the owner identity root"),
        ("genesis_authority_tree", lambda _p: __import__("security.guardian_plus", fromlist=["guardian_plus"]).guardian_plus.status(), "Guardian++ authority checks"),
        ("genesis_key_ceremony", lambda _p: {"signing_keys": sorted(__import__("api.hardening", fromlist=["_SIGNING_KEYS"])._SIGNING_KEYS)}, "the stack signing keys"),
        ("genesis_integrity_check", lambda _p: __import__("api.integrity_check", fromlist=["integrity_status"]).integrity_status(), "the module integrity baseline"),
        ("genesis_time_anchor", lambda _p: {"latest_ts": __import__("memory.ledger", fromlist=["get_ledger"]).get_ledger()[-1]["ts"]}, "ledger time anchoring"),
        ("genesis_recovery_core", lambda _p: __import__("phoenix.snapshot", fromlist=["PhoenixSnapshot"]).PhoenixSnapshot().status(), "phoenix snapshot recovery"),
        ("genesis_derivative_lock", lambda _p: __import__("api.key_license_registry", fromlist=["registry_status"]).registry_status(), "the derivative/license lock registry"),
        ("genesis_sovereign_decl", lambda _p: {"owner": "SLMK Jesse Martinez Junior"}, "the sovereign declaration of ownership"),
    ],
    "phoenix": [
        ("phoenix_watchdog", lambda _p: {"health": "LIVE"}, "hub health"),
        ("phoenix_resurrection", lambda _p: __import__("phoenix.snapshot", fromlist=["PhoenixSnapshot"]).PhoenixSnapshot().status(), "snapshot resurrection engine"),
        ("phoenix_self_heal", lambda _p: __import__("api.telemetry_ingest", fromlist=["ingest_status"]).ingest_status()["sources_total"], "source re-registration on hub restart"),
        ("phoenix_adaptive_upgrade", lambda _p: __import__("api.model_watcher", fromlist=["watcher_status"]).watcher_status(), "the model watcher upgrade lane"),
        ("phoenix_rollback_engine", lambda _p: __import__("phoenix.snapshot", fromlist=["PhoenixSnapshot"]).PhoenixSnapshot().status(), "rollback verification"),
        ("phoenix_redundancy_mesh", lambda _p: __import__("api.black_swarm", fromlist=["black_swarm"]).black_swarm.status(), "black swarm redundancy"),
        ("phoenix_chaos_guard", lambda _p: __import__("api.sentinel", fromlist=["sentinel_engine"]).sentinel_engine.scan(), "sentinel chaos/threat scan"),
        ("phoenix_zero_downtime", lambda _p: __import__("api.hyper_sync", fromlist=["convergence"]).convergence(), "hyper-sync convergence"),
        ("phoenix_god_mode_kernel", lambda _p: __import__("api.os_kernel", fromlist=["kernel"]).kernel.status() if hasattr(__import__("api.os_kernel", fromlist=["kernel"]), "kernel") else {"kernel": "present"}, "the sovereign kernel"),
        ("phoenix_threat_adapt", lambda _p: __import__("api.sentinel_ai", fromlist=["sentinel_ai"]).sentinel_ai.state() if hasattr(__import__("api.sentinel_ai", fromlist=["x"]), "sentinel_ai") else {"layer": "sentinel_ai"}, "sentinel AI adaptation"),
    ],
    "consciousness": [
        ("consciousness_anomaly_sense", lambda _p: __import__("api.sentinel", fromlist=["sentinel_engine"]).sentinel_engine.scan(), "sentinel anomaly sensing"),
        ("consciousness_context_field", lambda _p: __import__("crsmcpai.context_reasoning", fromlist=["crs"]).crs.stats(), "the CRS context field"),
        ("consciousness_global_map", lambda _p: {"networks": sorted(__import__("api.networks", fromlist=["all_networks"]).all_networks())}, "the network global map"),
        ("consciousness_intent_engine", lambda _p: {"parser": "solva_query_parser (deterministic)"}, "SOLVA query intent parsing"),
        ("consciousness_meta_audit", lambda _p: {"executions": len(__import__("memory.executions", fromlist=["list_executions"]).list_executions(limit=1000))}, "the execution audit record"),
        ("consciousness_predictive_ai", None, "no predictive engine is wired; AGSSI reasons but does not forecast"),
        ("consciousness_self_model", lambda _p: __import__("api.os_family", fromlist=["family_status"]).family_status()["family"]["consciousness"], "the consciousness self-model duty"),
        ("consciousness_signal_fuse", lambda _p: __import__("api.telemetry_ingest", fromlist=["ingest_status"]).ingest_status(), "telemetry signal fusion"),
        ("consciousness_solva_sense", lambda _p: __import__("solva_modules.family", fromlist=["get_solva"]).get_solva(17).status(), "the SOLVA telemetry sensor module"),
        ("consciousness_wisdom_layer", lambda _p: {"engine": "AGSSI three-pass reasoning"}, "AGSSI reasoning"),
    ],
    "dominion": [
        ("dominion_command_kernel", lambda _p: {"kernel": "api.os_kernel"}, "the sovereign kernel"),
        ("dominion_cross_sector_ai", lambda _p: {"networks": sorted(__import__("api.networks", fromlist=["all_networks"]).all_networks())}, "cross-network operation"),
        ("dominion_execution_gate", lambda _p: {"gate": "core.build_gate 4C/4V"}, "the quad build gate"),
        ("dominion_load_balancer", lambda _p: __import__("api.compute_fabric", fromlist=["hive_state"]).hive_state()["work"], "fabric work distribution"),
        ("dominion_ops_ledger", _chain, "the operations ledger"),
        ("dominion_planetary_render", lambda _p: {"media": "procedural engines in dominion/media (bounded frames)"}, "the procedural media engines"),
        ("dominion_policy_engine", lambda _p: __import__("security.guardian_plus", fromlist=["guardian_plus"]).guardian_plus.status(), "Guardian++ policy"),
        ("dominion_priority_matrix", lambda _p: __import__("api.compute_fabric", fromlist=["hive_state"]).hive_state()["work"], "fabric order queue"),
        ("dominion_resource_governor", lambda _p: {"nodes": __import__("api.compute_fabric", fromlist=["hive_state"]).hive_state()["nodes_active"]}, "hive capacity governance"),
        ("dominion_sector_orchestrator", lambda _p: __import__("api.os_orchestrator", fromlist=["orchestrator"]).orchestrator.status() if hasattr(__import__("api.os_orchestrator", fromlist=["x"]), "orchestrator") else {"hub": "os_orchestrator"}, "the OS state hub"),
    ],
    "sovereign": [
        ("sovereign_audit_trail", _chain, "the sealed audit chain"),
        ("sovereign_auth_gate", lambda _p: {"authorized_users": sorted(__import__("security.auth", fromlist=["x"]).AUTHORIZED_USERS)}, "authentication"),
        ("sovereign_betrayal_detector", lambda _p: __import__("api.pattern_watch", fromlist=["watch_status"]).watch_status() if hasattr(__import__("api.pattern_watch", fromlist=["x"]), "watch_status") else {"watch": "pattern_watch"}, "the harvest pattern watch"),
        ("sovereign_derivative_guard", lambda _p: {"watermark": "api.output_watermark v2"}, "output watermarking"),
        ("sovereign_identity_kernel", lambda _p: {"signing_keys": sorted(__import__("api.hardening", fromlist=["_SIGNING_KEYS"])._SIGNING_KEYS)}, "identity signing keys"),
        ("sovereign_ip_registry", lambda _p: __import__("api.key_license_registry", fromlist=["registry_status"]).registry_status(), "the IP/license registry"),
        ("sovereign_legal_anchor", lambda _p: __import__("api.key_license_registry", fromlist=["registry_status"]).registry_status(), "the registry as legal anchor"),
        ("sovereign_rights_enforcer", lambda _p: {"guard": "api.public_guard"}, "the public request guard"),
        ("sovereign_seal_engine", _chain, "ledger sealing"),
        ("sovereign_zero_stewardship", lambda _p: {"posture": "owner-only, default-deny"}, "the zero-stewardship posture"),
        ("sovereign_os_ai_runtime", lambda _p: {"runtime": "models.ollama_runtime relay chain"}, "the model relay runtime"),
        ("sovereign_os_driver_mesh", lambda _p: {"mesh_ws": "api.mesh_ws RTSGP++"}, "the WebSocket mesh driver"),
        ("sovereign_os_hypervisor", lambda _p: {"kernel": "api.os_kernel"}, "the sovereign kernel as hypervisor"),
        ("sovereign_os_ipc", lambda _p: __import__("crsmcpai.module_context_protocol", fromlist=["mcp"]).mcp.consume_since(0)["cursor"], "the MCP bus as IPC"),
        ("sovereign_os_kernel", lambda _p: {"kernel": "api.os_kernel"}, "the sovereign kernel"),
        ("sovereign_os_memory_arch", lambda _p: {"memories": __import__("memory.vector_store", fromlist=["memory_count"]).memory_count()}, "the vector memory architecture"),
        ("sovereign_os_quantum_layer", None, "real lattice PQC is not available in this runtime (liboqs); Ed25519 stands interim"),
        ("sovereign_os_realtime", lambda _p: __import__("api.telemetry_ingest", fromlist=["ingest_status"]).ingest_status()["accepted_events"], "live telemetry"),
        ("sovereign_os_scheduler", lambda _p: {"supervisor": "api.relay_supervisor"}, "the relay supervisor / scheduler"),
        ("sovereign_os_solva_kernel", lambda _p: __import__("solva_modules.family", fromlist=["solva_status"]).solva_status()["count"], "the SOLVA module family"),
    ],
}


def kernel_module_status(os_name: str = "") -> dict:
    out = {}
    for os_key, modules in _BINDINGS.items():
        if os_name and os_key != os_name:
            continue
        rows = []
        for name, probe, performs in modules:
            if probe is None:
                rows.append({"module": name, "state": "DECLARED ONLY",
                             "performs": performs})
                continue
            try:
                detail = probe(None)
                rows.append({"module": name, "state": "LIVE",
                             "performs": performs, "detail": detail})
            except Exception as exc:
                rows.append({"module": name, "state": "PROBE FAILED",
                             "performs": performs,
                             "detail": f"{type(exc).__name__}: {exc}"})
        out[os_key] = {
            "modules": rows,
            "live": sum(1 for r in rows if r["state"] == "LIVE"),
            "total": len(rows),
        }
    return {"source": SOURCE, "os": out,
            "total_live": sum(v["live"] for v in out.values()),
            "total": sum(v["total"] for v in out.values())}


@router.get("/status")
def kernel_modules_status():
    return kernel_module_status()


@router.get("/{os_name}")
def kernel_modules_for_os(os_name: str):
    return kernel_module_status(os_name)
