"""
CRSMCPAI Alpha - Autonomous Self-Upgrade & Hot-Patching Engine (crs.dominion.autoupdate)

Pushes verified, signed updates across the CRS network:
- Update package signature verification (HMAC-SHA256, constant-time compare)
- Semantic version comparison
- Staged patch plan generation (backup -> replace -> migrate -> verify)
- Rollback record creation for instant reversion

Crash-proof guarantees:
- Standard library only (hashlib, hmac, json, time)
- NO FastAPI / web imports
- NO module-level I/O, NO network calls at import time
- All functions defensive: bad input returns safe defaults, never raises

Built per Jesse AI specification, supreme hyper immaculate God mode standards.
Owner: SLMK Jesse Martinez Junior.
"""

import hashlib
import hmac
import json
import time

GENESIS_HASH = "92038cafccc7192535bd475cca985d03000d89962b8dc96f6664081663559b1b"


def _canonical(obj):
    try:
        return json.dumps(obj, sort_keys=True, separators=(",", ":"))
    except Exception:
        return ""


def sign_update_package(version, payload, secret_key):
    """Create a signed update package dict (helper for tests/producers)."""
    try:
        pkg = {
            "version": str(version),
            "payload": payload,
            "issued_at": int(time.time()),
            "genesis": GENESIS_HASH[:16],
        }
        canonical = _canonical({"version": pkg["version"], "payload": payload})
        key = str(secret_key).encode("utf-8", errors="ignore")
        pkg["signature"] = hmac.new(key, canonical.encode("utf-8"),
                                    hashlib.sha256).hexdigest()
        return pkg
    except Exception:
        return {"version": "0.0.0", "payload": {}, "signature": ""}


def verify_update_package(package, secret_key):
    """Authenticate an update package's HMAC-SHA256 signature. True if valid."""
    try:
        if not isinstance(package, dict):
            return False
        version = package.get("version")
        payload = package.get("payload")
        sig = package.get("signature")
        if not isinstance(version, str) or not isinstance(sig, str) or not sig:
            return False
        if payload is None:
            return False
        canonical = _canonical({"version": version, "payload": payload})
        if not canonical:
            return False
        key = str(secret_key).encode("utf-8", errors="ignore")
        expected = hmac.new(key, canonical.encode("utf-8"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, sig)
    except Exception:
        return False


def _parse_version(v):
    try:
        parts = str(v).strip().split(".")
        nums = []
        for p in parts[:4]:
            digits = "".join(c for c in p if c.isdigit())
            nums.append(int(digits) if digits else 0)
        while len(nums) < 3:
            nums.append(0)
        return nums
    except Exception:
        return [0, 0, 0]


def compare_versions(current_version, target_version):
    """Semantic version compare. -1 current<target, 0 equal, 1 current>target."""
    try:
        cur = _parse_version(current_version)
        tgt = _parse_version(target_version)
        if cur < tgt:
            return -1
        if cur > tgt:
            return 1
        return 0
    except Exception:
        a, b = str(current_version), str(target_version)
        if a < b:
            return -1
        if a > b:
            return 1
        return 0


_PATCH_ORDER = ("backup", "replace", "migrate", "verify", "restart")


def generate_patch_plan(manifest):
    """Order manifest actions into a safe staged execution plan.

    Manifest keys: files_to_update (list), migrations (list),
    restart_services (list), backups (list, optional).
    Returns ordered list of {step_id, action_type, payload} dicts.
    """
    try:
        if not isinstance(manifest, dict):
            return []
        steps = []

        def _lst(key):
            v = manifest.get(key)
            if isinstance(v, list):
                return [x for x in v if x is not None]
            return []

        backups = _lst("backups") or _lst("files_to_update")
        for i, item in enumerate(backups):
            steps.append({"step_id": f"backup-{i+1:03d}", "action_type": "backup",
                          "payload": item})
        for i, item in enumerate(_lst("files_to_update")):
            steps.append({"step_id": f"replace-{i+1:03d}", "action_type": "replace",
                          "payload": item})
        for i, item in enumerate(_lst("migrations")):
            steps.append({"step_id": f"migrate-{i+1:03d}", "action_type": "migrate",
                          "payload": item})
        steps.append({"step_id": "verify-001", "action_type": "verify",
                      "payload": {"check": "integrity"}})
        for i, item in enumerate(_lst("restart_services")):
            steps.append({"step_id": f"restart-{i+1:03d}", "action_type": "restart",
                          "payload": item})
        order = {name: idx for idx, name in enumerate(_PATCH_ORDER)}
        steps.sort(key=lambda s: (order.get(s["action_type"], 99), s["step_id"]))
        return steps
    except Exception:
        return []


def create_rollback_record(current_state_snapshot, target_version):
    """Build a rollback record before patching. Never raises."""
    try:
        try:
            snap = dict(current_state_snapshot) if isinstance(current_state_snapshot, dict) else {}
        except Exception:
            snap = {}
        return {
            "rollback_id": hashlib.sha256(
                (_canonical(snap) + str(time.time())).encode("utf-8")
            ).hexdigest()[:16],
            "created_at": int(time.time()),
            "target_version": str(target_version),
            "previous_state": snap,
            "genesis": GENESIS_HASH[:16],
            "status": "STAGED",
        }
    except Exception:
        return {"rollback_id": "error", "created_at": 0, "target_version": "0.0.0",
                "previous_state": {}, "status": "FAILED"}


def module_status():
    return {
        "module": "crs.dominion.autoupdate",
        "status": "ACTIVE",
        "genesis": GENESIS_HASH[:16],
        "functions": [
            "sign_update_package",
            "verify_update_package",
            "compare_versions",
            "generate_patch_plan",
            "create_rollback_record",
        ],
    }
