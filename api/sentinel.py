"""
CRSMCPAI Alpha — Sentinel Detection Engine (v1, 2026-11-08, Muse).

Real detection, replacing the static scan that always reported
threat_score 0 / NOMINAL regardless of traffic (the old
/guardian/sentinel/scan and the recovered sentinel_monitor.py both
returned constants). This engine evaluates actual events against
concrete rules and computes its state from what it has seen:

  R1 rate_spike            — one source emits more than RATE_LIMIT
                             events inside RATE_WINDOW seconds.
  R2 sequence_anomaly      — telemetry sequence numbers from a source
                             fail to strictly increase (replay or gap).
  R3 signature_failures    — SIGNATURE_FAILURE_LIMIT or more failed
                             signature/auth events from one source
                             inside the window.
  R4 unknown_source        — telemetry arrives from a source that is
                             not in the enrolled set (when an enrolled
                             set is known to the engine).
  R5 restricted_action     — a restricted action (the Guardian list:
                             DELETE_GENESIS, PURGE_LEDGER,
                             OVERRIDE_SLMK) is attempted by anyone
                             other than the owner.

threat_score is computed from alerts raised inside the last
SCORE_WINDOW seconds (severity points, capped at 100) and the state
(NOMINAL / ELEVATED / HIGH / CRITICAL) is derived from that score.
Nothing is hardcoded: quiet traffic scores 0 because the rules find
nothing, not because the answer is written in.

Events are plain dicts: {"ts": epoch seconds (optional, defaults to
now), "source": str, "kind": "telemetry"|"auth"|"command"|...,
"seq": int (telemetry), "ok": bool (auth/signature outcome),
"action": str, "user": str}. The engine is deliberately transport
agnostic: the mesh, the telemetry intake, or any caller can feed it.
Alerts are kept in a bounded in-process log and sealed to the ledger
on a best-effort basis.
"""
import threading
import time
from collections import defaultdict, deque

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from core.logger import log_event

OWNER = "jesse_martinez_jr"
RESTRICTED_ACTIONS = ("DELETE_GENESIS", "PURGE_LEDGER", "OVERRIDE_SLMK")

RATE_LIMIT = 60
RATE_WINDOW = 60.0
SIGNATURE_FAILURE_LIMIT = 3
SCORE_WINDOW = 600.0
MAX_ALERTS = 500

SEVERITY_POINTS = {"low": 5, "medium": 15, "high": 30, "critical": 50}


class SentinelEngine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events_seen = 0
        self._sources: set = set()
        self._enrolled: set = set()
        self._rate: dict = defaultdict(deque)        # source -> event times
        self._sig_fail: dict = defaultdict(deque)    # source -> failure times
        self._last_seq: dict = {}                    # source -> last seq
        self._alerts: deque = deque(maxlen=MAX_ALERTS)
        self._alert_counter = 0

    # ── configuration ──────────────────────────────────────────────────
    def enroll(self, source: str) -> None:
        with self._lock:
            self._enrolled.add(source)

    def set_enrolled(self, sources) -> None:
        with self._lock:
            self._enrolled = set(sources)

    # ── alert plumbing ─────────────────────────────────────────────────
    def _raise(self, rule: str, severity: str, source: str, detail: str, ts: float) -> dict:
        self._alert_counter += 1
        alert = {
            "id": self._alert_counter,
            "rule": rule,
            "severity": severity,
            "source": source,
            "detail": detail,
            "timestamp": ts,
        }
        self._alerts.append(alert)
        log_event(f"[SENTINEL] {rule} ({severity}) source={source}: {detail}", "warning")
        try:
            from memory.ledger import create_event
            create_event({"module": "SENTINEL", "event": "ALERT", **alert})
        except Exception:
            pass  # sealing is best-effort; detection does not depend on it
        return alert

    # ── core evaluation ────────────────────────────────────────────────
    def ingest(self, event: dict) -> list:
        """Evaluate one event; return the alerts it raised (maybe [])."""
        ts = float(event.get("ts") or time.time())
        source = str(event.get("source") or "unknown")
        kind = str(event.get("kind") or "generic")
        raised: list = []
        with self._lock:
            self._events_seen += 1
            self._sources.add(source)

            # R1 — rate spike per source
            window = self._rate[source]
            window.append(ts)
            while window and ts - window[0] > RATE_WINDOW:
                window.popleft()
            if len(window) == RATE_LIMIT + 1:
                raised.append(self._raise(
                    "rate_spike", "high", source,
                    f"{len(window)} events inside {int(RATE_WINDOW)}s (limit {RATE_LIMIT})", ts))

            # R2 — telemetry sequence must strictly increase per source
            if kind == "telemetry" and event.get("seq") is not None:
                seq = event["seq"]
                last = self._last_seq.get(source)
                if last is not None and seq <= last:
                    raised.append(self._raise(
                        "sequence_anomaly", "high", source,
                        f"sequence {seq} did not exceed last {last} (replay or reorder)", ts))
                elif last is not None and seq > last + 1:
                    raised.append(self._raise(
                        "sequence_anomaly", "medium", source,
                        f"sequence gap: last {last}, received {seq}", ts))
                self._last_seq[source] = max(seq, last if last is not None else seq)

            # R3 — signature / auth failure bursts
            if event.get("ok") is False and kind in ("auth", "signature", "telemetry"):
                fails = self._sig_fail[source]
                fails.append(ts)
                while fails and ts - fails[0] > RATE_WINDOW:
                    fails.popleft()
                if len(fails) == SIGNATURE_FAILURE_LIMIT:
                    raised.append(self._raise(
                        "signature_failures", "critical", source,
                        f"{len(fails)} failed verifications inside {int(RATE_WINDOW)}s", ts))

            # R4 — telemetry from an unenrolled source
            if kind == "telemetry" and self._enrolled and source not in self._enrolled:
                raised.append(self._raise(
                    "unknown_source", "medium", source,
                    "telemetry received from a source that is not enrolled", ts))

            # R5 — restricted action by a non-owner
            action = str(event.get("action") or "")
            user = str(event.get("user") or "")
            if action in RESTRICTED_ACTIONS and user != OWNER:
                raised.append(self._raise(
                    "restricted_action", "critical", source,
                    f"restricted action {action} attempted by '{user or 'anonymous'}'", ts))
        return raised

    def evaluate(self, events) -> list:
        """Batch-evaluate events; return every alert raised."""
        out: list = []
        for event in events or []:
            out.extend(self.ingest(event))
        return out

    # ── state ──────────────────────────────────────────────────────────
    def threat_score(self, now: float = None) -> int:
        now = now if now is not None else time.time()
        with self._lock:
            return min(100, sum(
                SEVERITY_POINTS[a["severity"]]
                for a in self._alerts
                if now - a["timestamp"] <= SCORE_WINDOW))

    def scan(self, now: float = None) -> dict:
        now = now if now is not None else time.time()
        score = self.threat_score(now)
        state = ("NOMINAL" if score == 0 else
                 "ELEVATED" if score < 30 else
                 "HIGH" if score < 70 else "CRITICAL")
        with self._lock:
            active = [a for a in self._alerts if now - a["timestamp"] <= SCORE_WINDOW]
            return {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
                "monitoring": True,
                "threat_score": score,
                "state": state,
                "events_seen": self._events_seen,
                "sources_seen": len(self._sources),
                "alerts_active": len(active),
                "alerts_total": len(self._alerts),
                "engine": "sentinel-detection-v1",
            }

    def alerts(self, limit: int = 50) -> list:
        with self._lock:
            return list(self._alerts)[-limit:]


# Shared engine instance: the /sentinel routes and the legacy
# /guardian/sentinel/scan route both read this one, so every surface
# reports the same computed truth.
sentinel_engine = SentinelEngine()

sentinel_router = APIRouter(prefix="/sentinel", tags=["sentinel"])


@sentinel_router.post("/ingest")
async def sentinel_ingest(request: dict):
    events = request.get("events") or []
    raised = sentinel_engine.evaluate(events)
    return JSONResponse(content={
        "ingested": len(events),
        "alerts_raised": raised,
        "scan": sentinel_engine.scan(),
    })


@sentinel_router.get("/scan")
async def sentinel_scan_v2():
    return JSONResponse(content=sentinel_engine.scan())


@sentinel_router.get("/alerts")
async def sentinel_alerts():
    return JSONResponse(content={"alerts": sentinel_engine.alerts()})


@sentinel_router.get("/status")
async def sentinel_status():
    return JSONResponse(content={
        "module": "SENTINEL",
        "engine": "sentinel-detection-v1",
        "rules": ["rate_spike", "sequence_anomaly", "signature_failures",
                  "unknown_source", "restricted_action"],
        "scan": sentinel_engine.scan(),
    })
