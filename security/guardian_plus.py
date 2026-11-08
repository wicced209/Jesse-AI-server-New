"""
CRSMCPAI Alpha — Guardian++ (v1, 2026-11-08, Muse).

The enhanced guardian layer, built from the recovered spec (Guardian++
sat at EXISTENCE UNCONFIRMED in the recovery record — descriptions
only, no module code anywhere we hold). Where the base guardian agent
authenticates, signs, and verifies, Guardian++ runs the full gate in
one verdict, every check real:

  1. AUTHENTICATION — the user must be authorized (security.auth,
     owner-only set).
  2. RBAC — the recovered Guardian AI rule, integrated: the owner
     holds absolute override; the restricted actions (DELETE_GENESIS,
     PURGE_LEDGER, OVERRIDE_SLMK) are denied to everyone else; all
     other actions pass this layer.
  3. SIGNATURE — when the caller presents a signature over the
     payload, it must verify through PQSVM (the real Ed25519 check,
     fail closed). A bad signature denies the request outright.
  4. VELOCITY — per-user action counts inside a rolling window; a
     burst beyond the limit denies and raises a Sentinel alert.
  5. SENTINEL — restricted-action attempts and velocity bursts are fed
     to the Sentinel detection engine as events, so the watch layer
     sees what the gate refused.

The verdict is a dict naming every check and every reason; denial
always carries its reason. Verdicts are sealed to the ledger on a
best-effort basis. Fail closed throughout: an exception in any check
is a denial, never a pass.
"""
import threading
import time
from collections import defaultdict, deque

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from core.logger import log_event
from security.auth import authenticate

OWNER = "jesse_martinez_jr"
RESTRICTED_ACTIONS = ("DELETE_GENESIS", "PURGE_LEDGER", "OVERRIDE_SLMK")
VELOCITY_LIMIT = 30
VELOCITY_WINDOW = 60.0


class GuardianPlusPlus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._actions: dict = defaultdict(deque)   # user -> action times
        self._verdicts = 0
        self._denials = 0

    # ── individual checks ──────────────────────────────────────────────
    def _check_rbac(self, user: str, action: str) -> tuple:
        if user == OWNER:
            return True, "owner absolute override"
        if action in RESTRICTED_ACTIONS:
            return False, f"restricted action {action} is owner-only"
        return True, "action permitted for authorized user"

    def _check_velocity(self, user: str, ts: float) -> tuple:
        with self._lock:
            window = self._actions[user]
            window.append(ts)
            while window and ts - window[0] > VELOCITY_WINDOW:
                window.popleft()
            count = len(window)
        if count > VELOCITY_LIMIT:
            return False, count
        return True, count

    # ── the gate ───────────────────────────────────────────────────────
    def validate(self, user: str, action: str, payload: str = "",
                 signature: str = None, source: str = "guardian-plus") -> dict:
        ts = time.time()
        checks: dict = {}
        reasons: list = []

        # 1. Authentication
        try:
            authed = bool(authenticate(user))
        except Exception:
            authed = False
        checks["authentication"] = authed
        if not authed:
            reasons.append(f"user '{user}' is not authorized")

        # 2. RBAC (recovered Guardian AI rule)
        rbac_ok, rbac_note = self._check_rbac(user, action)
        checks["rbac"] = rbac_ok
        if not rbac_ok:
            reasons.append(rbac_note)

        # 3. Signature, when presented — real PQSVM verification
        if signature is not None:
            try:
                from crsmcpai.pqsvm import pqsvm_verify
                sig_ok = bool(pqsvm_verify(payload, signature).get("valid"))
            except Exception:
                sig_ok = False
            checks["signature"] = sig_ok
            if not sig_ok:
                reasons.append("signature did not verify (PQSVM)")

        # 4. Velocity
        vel_ok, vel_count = self._check_velocity(user, ts)
        checks["velocity"] = vel_ok
        if not vel_ok:
            reasons.append(
                f"velocity limit exceeded: {vel_count} actions inside "
                f"{int(VELOCITY_WINDOW)}s (limit {VELOCITY_LIMIT})")

        allowed = authed and rbac_ok and vel_ok and checks.get("signature", True)

        with self._lock:
            self._verdicts += 1
            if not allowed:
                self._denials += 1

        verdict = {
            "allowed": allowed,
            "user": user,
            "action": action,
            "checks": checks,
            "reasons": reasons,
            "override": "SLMK_ABSOLUTE" if (allowed and user == OWNER) else None,
            "timestamp": ts,
        }

        # 5. Feed refusals that matter to the Sentinel watch layer
        if not allowed and (not rbac_ok or not vel_ok):
            try:
                from api.sentinel import sentinel_engine
                sentinel_engine.ingest({
                    "ts": ts, "source": source, "kind": "command",
                    "action": action, "user": user, "ok": False,
                })
            except Exception:
                pass

        try:
            from memory.ledger import create_event
            create_event({"module": "GUARDIAN_PP", "event": "VERDICT",
                          "user": user, "action": action, "allowed": allowed})
        except Exception:
            pass

        log_event(f"[GUARDIAN++] user={user} action={action} allowed={allowed}"
                  + (f" reasons={reasons}" if reasons else ""))
        return verdict

    def status(self) -> dict:
        with self._lock:
            return {
                "module": "GUARDIAN_PP",
                "version": "v1 (built 2026-11-08)",
                "checks": ["authentication", "rbac", "signature (PQSVM)",
                           "velocity", "sentinel feed"],
                "verdicts": self._verdicts,
                "denials": self._denials,
                "restricted_actions": list(RESTRICTED_ACTIONS),
            }


guardian_plus = GuardianPlusPlus()

guardian_plus_router = APIRouter(prefix="/guardian-plus", tags=["guardian-plus"])


@guardian_plus_router.post("/validate")
async def guardian_plus_validate(request: dict):
    verdict = guardian_plus.validate(
        user=str(request.get("user") or ""),
        action=str(request.get("action") or ""),
        payload=str(request.get("payload") or ""),
        signature=request.get("signature"),
        source=str(request.get("source") or "guardian-plus"),
    )
    return JSONResponse(content=verdict)


@guardian_plus_router.get("/status")
async def guardian_plus_status():
    return JSONResponse(content=guardian_plus.status())
