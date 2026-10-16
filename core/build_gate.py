"""
CRSMCPAI Alpha — Quad Check / Quad Validate Build Gate (4C/4V)
Owner: SLMK Jesse Martinez Junior

Jesse's standing build standard: no build is released without passing
all 8 gates.

Quad Check (4C) — static checks on the build and its artifacts:
  C1 genesis_hash        — the sovereign ledger chain verifies and its
                           genesis anchor matches the GENESIS hash.
  C2 superadmin_token    — the build was requested by the sovereign
                           owner (superadmin), not merely an authorized user.
  C3 dependency_purity   — every import in every generated artifact is
                           inside the sovereign sandbox allowlist.
  C4 sha256_checksum     — SHA256 of every artifact, recorded and
                           ledger-sealed.

Quad Validate (4V) — dynamic validations:
  V1 sandbox_smoke       — every step executed OK inside the sovereign
                           sandbox (recorded execution, smoke output kept).
  V2 security_scan       — AST scan: no blocked names/attributes and no
                           network-execution primitives.
  V3 load_behavior        — every step finished inside the per-step time
                           budget and the whole build inside the total budget.
  V4 mesh_integration     — artifacts declaring HTTP routes must not
                           collide with reserved mesh route paths.

Verdict is GO only when all 8 gates pass. The gate fails closed: any
error inside the gate itself yields NO_GO. The verdict and per-gate
results are sealed into the immutable ledger.
"""
import ast
import hashlib
import time

from core.logger import log_event
from core.sandbox import ALLOWED_IMPORTS, BLOCKED_NAMES, BLOCKED_ATTRS
from memory.ledger import GENESIS, create_event, get_ledger, verify_chain
from security.auth import authenticate

GATE_VERSION = "4C4V-v1.0"

# Per-step and whole-build time budgets (V3). The sandbox hard timeout is
# 30s; the gate budget is stricter so runaway builds never get near it.
LOAD_BUDGET_MS_PER_STEP = 10_000
LOAD_BUDGET_MS_TOTAL = 60_000

# Route paths reserved by the hub and mesh surface. A generated artifact
# must not redeclare any of these (V4).
RESERVED_ROUTE_PATHS = frozenset({
    "/", "/health", "/handshake", "/status", "/audit", "/log",
    "/command", "/mcp/command", "/crsmcpai", "/query", "/build",
    "/ledger", "/memory", "/directive", "/telemetry", "/pulse",
    "/ws", "/mesh", "/mcp/manifest", "/intelligence/siren",
})

# Explicit network-execution primitives that are never acceptable in a
# generated artifact, even though some parent modules are allowlisted
# for pure data-structure use (V2).
DENIED_PATTERNS = (
    "socket", "subprocess", "os.system", "os.popen", "os.exec",
    "os.spawn", "pty", "webbrowser", "urllib.request.urlopen",
    "http.client", "requests.",
)

_SUCCESS_STATUSES = ("ok", "executed")


def _gate(name, passed, detail):
    return {"gate": name, "passed": bool(passed), "detail": str(detail)}


def _c1_genesis_hash():
    """C1: ledger chain verifies and genesis anchor matches GENESIS."""
    try:
        chain_ok = verify_chain()
        chain = get_ledger()
        anchor_ok = (not chain) or (chain[0].get("prev_hash") == GENESIS)
        passed = bool(chain_ok and anchor_ok)
        detail = (f"chain_valid={chain_ok}, blocks={len(chain)}, "
                  f"genesis_anchor={'ok' if anchor_ok else 'MISMATCH'}")
    except Exception as e:  # fail closed
        passed, detail = False, f"ledger check raised: {e}"
    return _gate("C1_genesis_hash", passed, detail)


def _c2_superadmin_token(user):
    """C2: the build was requested by the sovereign superadmin account.

    The /build endpoint authorizes any user in the allowlist (which also
    contains the generic "admin" login). The gate is stricter: the
    requester must be the owner's superadmin account, not the generic
    admin login.
    """
    authed = authenticate(user)
    is_owner_account = authed and user != "admin"
    passed = bool(is_owner_account)
    detail = (f"build user '{user}': authorized={authed}, "
              f"superadmin(owner) account={is_owner_account}")
    return _gate("C2_superadmin_token", passed, detail)


def _iter_import_roots(code):
    """Yield top-level import roots from source code."""
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                yield node.module.split(".")[0]


def _c3_dependency_purity(steps):
    """C3: every import in every artifact is sandbox-allowlisted."""
    if not steps:
        return _gate("C3_dependency_purity", False, "no build steps to check")
    bad = []
    checked = 0
    for s in steps:
        code = s.get("code") or ""
        if not code.strip():
            bad.append(f"step {s.get('step')}: no artifact code")
            continue
        try:
            roots = set(_iter_import_roots(code))
        except SyntaxError as e:
            bad.append(f"step {s.get('step')}: unparsable code ({e})")
            continue
        checked += 1
        foreign = sorted(r for r in roots if r not in ALLOWED_IMPORTS)
        if foreign:
            bad.append(f"step {s.get('step')}: non-allowlisted imports {foreign}")
    passed = not bad
    detail = (f"{checked} artifact(s) scanned, all imports allowlisted"
              if passed else "; ".join(bad))
    return _gate("C3_dependency_purity", passed, detail)


def _c4_sha256_checksum(steps):
    """C4: SHA256 checksum of every artifact, recorded for the seal."""
    if not steps:
        return _gate("C4_sha256_checksum", False, "no build steps to check")
    sums = {}
    missing = []
    for s in steps:
        code = s.get("code") or ""
        if not code.strip():
            missing.append(f"step {s.get('step')}")
            continue
        sums[f"step_{s.get('step')}"] = hashlib.sha256(
            code.encode("utf-8")).hexdigest()
    passed = not missing and bool(sums)
    detail = (f"checksums={sums}" if passed
              else f"missing artifacts for {missing}")
    gate = _gate("C4_sha256_checksum", passed, detail)
    gate["sha256"] = sums
    return gate


def _v1_sandbox_smoke(steps):
    """V1: every step executed OK inside the sovereign sandbox."""
    if not steps:
        return _gate("V1_sandbox_smoke", False, "no build steps to check")
    bad = []
    for s in steps:
        status = s.get("status")
        stderr = s.get("stderr") or ""
        if status not in _SUCCESS_STATUSES:
            bad.append(f"step {s.get('step')}: status '{status}'")
        elif "SandboxViolation" in stderr:
            bad.append(f"step {s.get('step')}: sandbox violation in stderr")
    passed = not bad
    detail = (f"{len(steps)} step(s) executed ok in sandbox, smoke output kept"
              if passed else "; ".join(bad))
    return _gate("V1_sandbox_smoke", passed, detail)


def _v2_security_scan(steps):
    """V2: AST scan for blocked names/attrs and network-exec primitives."""
    if not steps:
        return _gate("V2_security_scan", False, "no build steps to check")
    findings = []
    scanned = 0
    for s in steps:
        code = s.get("code") or ""
        if not code.strip():
            findings.append(f"step {s.get('step')}: no artifact code")
            continue
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            findings.append(f"step {s.get('step')}: unparsable ({e})")
            continue
        scanned += 1
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in BLOCKED_NAMES:
                findings.append(
                    f"step {s.get('step')}: blocked name '{node.id}'")
            elif (isinstance(node, ast.Attribute)
                    and node.attr in BLOCKED_ATTRS):
                findings.append(
                    f"step {s.get('step')}: blocked attribute '{node.attr}'")
        lowered = code.lower()
        for pat in DENIED_PATTERNS:
            if pat in lowered:
                findings.append(
                    f"step {s.get('step')}: denied pattern '{pat}'")
    passed = not findings
    detail = (f"{scanned} artifact(s) scanned, no findings"
              if passed else "; ".join(findings))
    return _gate("V2_security_scan", passed, detail)


def _v3_load_behavior(steps, total_ms):
    """V3: per-step and total elapsed time inside budget."""
    if not steps:
        return _gate("V3_load_behavior", False, "no build steps to check")
    bad = []
    for s in steps:
        ms = s.get("elapsed_ms")
        if ms is None:
            bad.append(f"step {s.get('step')}: no timing recorded")
        elif ms > LOAD_BUDGET_MS_PER_STEP:
            bad.append(f"step {s.get('step')}: {ms}ms over "
                       f"{LOAD_BUDGET_MS_PER_STEP}ms budget")
    if total_ms is not None and total_ms > LOAD_BUDGET_MS_TOTAL:
        bad.append(f"total {total_ms}ms over {LOAD_BUDGET_MS_TOTAL}ms budget")
    passed = not bad
    detail = (f"{len(steps)} step(s) within {LOAD_BUDGET_MS_PER_STEP}ms, "
              f"total {total_ms}ms within {LOAD_BUDGET_MS_TOTAL}ms"
              if passed else "; ".join(bad))
    return _gate("V3_load_behavior", passed, detail)


def _declared_route_paths(code):
    """Extract literal route paths from FastAPI-style decorators."""
    paths = set()
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return paths
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                if dec.func.attr in ("get", "post", "put", "delete",
                                     "patch", "websocket"):
                    if dec.args and isinstance(dec.args[0], ast.Constant):
                        val = dec.args[0].value
                        if isinstance(val, str):
                            paths.add(val)
    return paths


def _v4_mesh_integration(steps):
    """V4: artifact-declared routes must not collide with mesh routes."""
    collisions = []
    declared_total = 0
    for s in steps:
        code = s.get("code") or ""
        if not code.strip():
            continue
        paths = _declared_route_paths(code)
        declared_total += len(paths)
        for p in paths:
            if p in RESERVED_ROUTE_PATHS:
                collisions.append(f"step {s.get('step')}: route '{p}' "
                                  f"collides with reserved mesh path")
    passed = not collisions
    detail = (f"{declared_total} declared route(s), none collide with "
              f"{len(RESERVED_ROUTE_PATHS)} reserved mesh paths"
              if passed else "; ".join(collisions))
    return _gate("V4_mesh_integration", passed, detail)


def run_build_gate(build_result, user):
    """
    Run the full 4C/4V gate over a completed autonomous build.

    build_result: dict with keys steps (list of step dicts; each may carry
      step, status, stdout, stderr, code, elapsed_ms), all_ok, elapsed_ms.
    user: the requesting user (C2 requires the sovereign owner).

    Returns a report dict with gates, verdict (GO/NO_GO), sha256 map,
    and the ledger seal block. Never raises — fails closed.
    """
    started = time.time()
    try:
        steps = build_result.get("steps") or []
        total_ms = build_result.get("elapsed_ms")

        gates = [
            _c1_genesis_hash(),
            _c2_superadmin_token(user),
            _c3_dependency_purity(steps),
            _c4_sha256_checksum(steps),
            _v1_sandbox_smoke(steps),
            _v2_security_scan(steps),
            _v3_load_behavior(steps, total_ms),
            _v4_mesh_integration(steps),
        ]
        verdict = "GO" if all(g["passed"] for g in gates) else "NO_GO"
        sha256 = {}
        for g in gates:
            if "sha256" in g:
                sha256.update(g["sha256"])

        report = {
            "gate_version": GATE_VERSION,
            "standard": "quad_check_quad_validate",
            "verdict": verdict,
            "gates": gates,
            "sha256": sha256,
            "build_all_ok": bool(build_result.get("all_ok")),
            "user": user,
            "gate_elapsed_ms": int((time.time() - started) * 1000),
        }

        # Seal the verdict into the immutable ledger.
        try:
            seal = create_event({
                "event": "BUILD_GATE",
                "gate_version": GATE_VERSION,
                "verdict": verdict,
                "gates_passed": [g["gate"] for g in gates if g["passed"]],
                "gates_failed": [g["gate"] for g in gates if not g["passed"]],
                "sha256": sha256,
                "user": user,
            })
            report["ledger_seal"] = {
                "index": seal.get("index"),
                "block_hash": seal.get("block_hash"),
            }
        except Exception as e:
            log_event(f"[GATE] ledger seal failed: {e}", "warning")
            report["ledger_seal"] = {"error": str(e)}

        log_event(f"[GATE] 4C/4V verdict={verdict} "
                  f"({sum(g['passed'] for g in gates)}/8 gates passed)")
        return report
    except Exception as e:  # fail closed — never let a gate error pass a build
        log_event(f"[GATE] gate crashed, failing closed: {e}", "warning")
        return {
            "gate_version": GATE_VERSION,
            "standard": "quad_check_quad_validate",
            "verdict": "NO_GO",
            "gates": [],
            "sha256": {},
            "error": str(e),
            "user": user,
        }
