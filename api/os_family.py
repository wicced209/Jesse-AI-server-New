"""
CRSMCPAI Alpha — OS Family Behavior Layer (v1, 2026-11-08, Muse).

The six sovereign operating systems — Genesis, Phoenix, Consciousness,
Dominion, Sovereign, and Sovereign Dominion — have lived in this stack
as registry entries whose boot flipped a state string and stamped a
hash. This layer gives each OS its actual job, executed against the
real components at run time:

  Genesis OS        verifies the foundation: the ledger's first block
                    hangs on the GENESIS anchor, the whole chain
                    verifies, the hyper-sync fingerprint agrees, and
                    the sovereign kernel spawns and schedules a task.
  Phoenix OS        runs a resurrection drill: snapshots the live
                    system state with the real Phoenix snapshot
                    engine, proves the snapshot matches the present
                    state, and proves a mutated state is detected.
  Consciousness OS  builds the stack's self-model from live probes
                    (ledger, telemetry, networks, sentinel, sync,
                    voice, OS states) and diffs it against the
                    previous model, reporting exactly what changed.
  Dominion OS       exercises the governance gates it exists to
                    enforce: Guardian++ adjudication (owner override
                    allowed, stranger denied) and the Dominion terms
                    check on the mesh.
  Sovereign OS      audits identity: the key/license registry state,
                    the registered signing keys, and a live
                    sign-and-verify round trip through PQSVM.
  Sovereign Dominion OS  the apex: runs the other five duties in
                    boot order and issues one composite verdict.

An OS is reported ACTIVE in this layer only when its duty passes.
Every run is sealed to the Golden Ledger, best-effort. The layer
drives its own OSOrchestrator instance (the hub's lifecycle registry);
the pre-existing /os routes keep theirs — states are read from this
layer's runs, and the docstring says so rather than pretending the
two registries are one.

Owner: SLMK Jesse Martinez Junior.
"""
import time
from typing import Any, Dict

from fastapi import APIRouter
from pydantic import BaseModel

from api.os_orchestrator import OS_REGISTRY, OSOrchestrator
from core.logger import log_event

router = APIRouter(prefix="/os-family", tags=["os-family"])

_orchestrator = OSOrchestrator()
_last_runs: Dict[str, Dict[str, Any]] = {}
_last_awareness: Dict[str, Any] = {}


def _seal(os_key: str, duty: str, passed: bool, detail: Dict[str, Any]) -> None:
    try:
        from memory.ledger import create_event
        create_event({"module": "OS_FAMILY", "os": os_key, "duty": duty,
                      "passed": passed, "detail": detail})
    except Exception:
        pass


def _check(name: str, ok: bool, detail: Any = None) -> Dict[str, Any]:
    return {"check": name, "ok": bool(ok), "detail": detail}


# ── Duties ─────────────────────────────────────────────────────────────

def duty_genesis() -> Dict[str, Any]:
    from memory.ledger import GENESIS, get_ledger, verify_chain
    from api.hyper_sync import local_fingerprint
    from api.os_kernel import SovereignKernel
    chain = get_ledger()
    fp = local_fingerprint()
    kernel = SovereignKernel()
    pid = kernel.spawn_task("genesis-verify", "GENESIS", 10, {"SYS_EXEC"})
    cap_ok = kernel.check_capability(pid, "SYS_EXEC") if pid >= 0 else False
    kernel.scheduler_tick()
    checks = [
        _check("genesis_anchor", bool(chain) and chain[0]["prev_hash"] == GENESIS,
               "first block hangs on the GENESIS anchor"),
        _check("chain_verifies", verify_chain()),
        _check("sync_fingerprint_agrees", fp["genesis"] == GENESIS and fp["height"] == len(chain),
               f"height {fp['height']}"),
        _check("kernel_spawns_and_schedules", pid >= 0 and cap_ok,
               f"pid {pid}, capability SYS_EXEC granted"),
    ]
    return {"duty": "genesis_verification", "checks": checks,
            "passed": all(c["ok"] for c in checks)}


def _system_state() -> Dict[str, Any]:
    """The compact live state Phoenix snapshots and Consciousness
    models: small, JSON-stable, and entirely measured."""
    from memory.ledger import get_ledger, verify_chain
    from api import telemetry_ingest
    from api.hyper_sync import local_fingerprint
    chain = get_ledger()
    tel = telemetry_ingest.ingest_status()
    fp = local_fingerprint()
    return {
        "ledger_height": len(chain),
        "ledger_head": fp["head"],
        "ledger_root": fp["root"],
        "chain_valid": verify_chain(),
        "telemetry_sources": tel["sources_total"],
        "telemetry_events": tel["accepted_events"],
    }


def duty_phoenix() -> Dict[str, Any]:
    from phoenix.snapshot import PhoenixSnapshot
    engine = PhoenixSnapshot()
    state = _system_state()
    snap = engine.snapshot("os-family-drill", state)
    verify = engine.rollback_verify(snap["snapshot_id"], state)
    mutated = dict(state, ledger_height=state["ledger_height"] + 999)
    verify_mutated = engine.rollback_verify(snap["snapshot_id"], mutated)
    checks = [
        _check("snapshot_taken", bool(snap.get("snapshot_id")), snap.get("snapshot_id")),
        _check("snapshot_matches_present_state", verify.get("matches_snapshot") is True),
        _check("mutation_detected", verify_mutated.get("matches_snapshot") is False,
               "a state differing from the snapshot does not verify against it"),
        _check("lattice_health_proof", bool(engine.lattice_health_proof())),
    ]
    return {"duty": "resurrection_drill", "checks": checks,
            "snapshot_id": snap.get("snapshot_id"),
            "passed": all(c["ok"] for c in checks)}


def _self_model() -> Dict[str, Any]:
    model = {"system_state": _system_state()}
    try:
        from api.sentinel import sentinel_engine
        model["sentinel"] = sentinel_engine.scan()["state"]
    except Exception:
        model["sentinel"] = "unreachable"
    try:
        from api.networks import all_networks
        nets = all_networks()["networks"]
        model["networks_bound"] = {k: v.get("bound_live") for k, v in nets.items()}
    except Exception:
        model["networks_bound"] = "unreachable"
    try:
        from api.hyper_sync import convergence
        model["sync_peers"] = convergence()["peers"]
    except Exception:
        model["sync_peers"] = "unreachable"
    model["os_states"] = {k: v["status"] for k, v in
                          _orchestrator.overview()["os"].items()}
    return model


def duty_consciousness() -> Dict[str, Any]:
    global _last_awareness
    model = _self_model()
    changed = []
    if _last_awareness:
        for key, value in model.items():
            if _last_awareness.get(key) != value:
                changed.append(key)
    first = not _last_awareness
    _last_awareness = model
    checks = [
        _check("self_model_built", bool(model.get("system_state"))),
        _check("ledger_in_model", model["system_state"].get("chain_valid") is True),
    ]
    return {"duty": "awareness", "checks": checks, "passed": all(c["ok"] for c in checks),
            "first_awareness": first, "changed_since_last": changed, "model": model}


def duty_dominion() -> Dict[str, Any]:
    from security.guardian_plus import guardian_plus
    from api.mesh_ws import dominion_terms_check
    owner = guardian_plus.validate("jesse_martinez_jr", "PURGE_LEDGER")
    stranger = guardian_plus.validate("mallory", "PURGE_LEDGER")
    checks = [
        _check("owner_override_allowed", owner["allowed"] and owner["override"] == "SLMK_ABSOLUTE",
               owner["reasons"]),
        _check("stranger_denied", not stranger["allowed"], stranger["reasons"]),
        _check("dominion_terms_gate", dominion_terms_check("CRSMCPAI_ALPHA_CORE", "HEARTBEAT") is True),
    ]
    return {"duty": "governance_adjudication", "checks": checks,
            "passed": all(c["ok"] for c in checks)}


def duty_sovereign() -> Dict[str, Any]:
    from api.key_license_registry import registry_status
    from api.hardening import _SIGNING_KEYS
    from security.crypto import sign_data
    from crsmcpai.pqsvm import pqsvm_verify
    status = registry_status()
    payload = f"os-family-sovereign-audit:{int(time.time())}"
    signature = sign_data(payload.encode())
    verdict = pqsvm_verify(payload, signature)
    checks = [
        _check("registry_readable", isinstance(status, dict)),
        _check("signing_keys_registered", "jesse_martinez_jr" in _SIGNING_KEYS,
               list(_SIGNING_KEYS.keys())),
        _check("identity_crypto_roundtrip", bool(verdict.get("valid")), verdict),
    ]
    return {"duty": "identity_audit", "checks": checks,
            "registry": status, "passed": all(c["ok"] for c in checks)}


DUTIES = {
    "genesis": duty_genesis,
    "phoenix": duty_phoenix,
    "consciousness": duty_consciousness,
    "dominion": duty_dominion,
    "sovereign": duty_sovereign,
}


def run_os(key: str) -> Dict[str, Any]:
    key = (key or "").lower()
    if key == "sovereign-dominion":
        return run_full_check()
    if key not in DUTIES:
        return {"ok": False, "error": f"unknown OS '{key}'", "known": list(OS_REGISTRY)}
    boot = _orchestrator.boot(key)
    try:
        result = DUTIES[key]()
    except Exception as exc:
        result = {"duty": "error", "passed": False,
                  "checks": [_check("duty_executed", False, f"{type(exc).__name__}: {exc}")]}
    record = {"os": key, "name": OS_REGISTRY[key]["name"], "boot": boot,
              "result": result, "passed": result.get("passed", False),
              "timestamp": time.time()}
    _last_runs[key] = record
    if not record["passed"]:
        _orchestrator.suspend(key)
    _seal(key, result.get("duty", "?"), record["passed"],
          {"checks": [c["check"] for c in result.get("checks", [])]})
    log_event(f"[OS-FAMILY] {key} duty {result.get('duty')}: "
              f"{'PASS' if record['passed'] else 'FAIL'}")
    return {"ok": True, **record}


def run_full_check() -> Dict[str, Any]:
    """Sovereign Dominion OS: the other five duties in boot order,
    one composite verdict."""
    order = sorted(DUTIES.keys(), key=lambda k: OS_REGISTRY[k]["boot_order"])
    results = {}
    for key in order:
        results[key] = run_os(key)
    boot = _orchestrator.boot("sovereign-dominion")
    passed = all(r["passed"] for r in results.values())
    if not passed:
        _orchestrator.suspend("sovereign-dominion")
    record = {"os": "sovereign-dominion", "name": OS_REGISTRY["sovereign-dominion"]["name"],
              "boot": boot, "passed": passed,
              "result": {"duty": "full_system_check",
                         "checks": [_check(k, r["passed"]) for k, r in results.items()]},
              "sub_results": {k: r["result"] for k, r in results.items()},
              "timestamp": time.time()}
    _last_runs["sovereign-dominion"] = record
    _seal("sovereign-dominion", "full_system_check", passed,
          {"subsystems": {k: r["passed"] for k, r in results.items()}})
    return {"ok": True, **record}


def family_status() -> Dict[str, Any]:
    overview = _orchestrator.overview()
    out = {}
    for key, info in OS_REGISTRY.items():
        run = _last_runs.get(key)
        out[key] = {
            "name": info["name"], "role": info["role"], "boot_order": info["boot_order"],
            "lifecycle": overview["os"][key]["status"],
            "last_duty": run["result"]["duty"] if run else None,
            "last_passed": run["passed"] if run else None,
            "last_run": run["timestamp"] if run else None,
        }
    return {"family": out, "orchestrator_healthy": _orchestrator.health_check()["ok"],
            "timestamp": time.time()}


# ── Routes ─────────────────────────────────────────────────────────────

class RunRequest(BaseModel):
    os: str


@router.get("/status")
def os_family_status():
    return family_status()


@router.post("/run")
def os_family_run(req: RunRequest):
    return run_os(req.os)


@router.post("/full-check")
def os_family_full_check():
    return run_full_check()


@router.get("/awareness")
def os_family_awareness():
    return _last_awareness or {"note": "Consciousness OS has not run its awareness duty yet"}
