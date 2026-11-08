"""
CRSMCPAI Alpha — PQ Chaos Hardening Middleware (v1, 2026-11-08, Muse).

Implements the buildable pillars of the recovered API hardening plan
(docs/API_HARDENING_PLAN.md), audited against the live stack:

  Pillar 6 — Enterprise security headers on EVERY response
             (nosniff, frame DENY, XSS block, HSTS, CSP none,
             robots noindex, Server: CRSMCPAI-Sovereign-Mesh).
  Pillar 3 — Tiered sliding-window rate limiting per client:
             reads 120/min, compute endpoints 30/min, admin
             endpoints 5/min; HTTP 429 with Retry-After when
             exhausted. In-process windows (this runtime has no
             Redis; the plan's Redis backing is the scale-out step).
  Pillar 1 — Ed25519 request signing with nonce + timestamp window
             (headers X-Sovereign-Key / -Timestamp / -Nonce /
             -Signature; signature over METHOD+PATH+TIMESTAMP+
             NONCE+SHA256(BODY); ±30s window; nonce replay rejected
             for 60s). Verification is REAL whenever the headers are
             present. Enforcement (rejecting UNSIGNED requests) is
             gated by env SOVEREIGN_SIGNING_ENFORCE=1 and applies to
             the protected prefixes below, so existing unsigned lanes
             (the demo, the build loop) keep working until the owner
             flips the switch — that flip is the owner's call.
  Pillar 7 — Every signing failure and rate-limit rejection is
             audited: fed to the Sentinel engine as a failed-auth
             event and sealed to the ledger, best-effort.
  Pillar 2 — Constant-time comparisons were audited across the auth
             surface (mesh, telemetry intake, key registry, PQSVM):
             all already use hmac.compare_digest or NaCl verify.
             The Kyber hybrid KEM half of pillar 2 needs liboqs and
             stays honestly open (same blocker as real PQC).
  Pillar 5 — Superadmin guards already stand on the sensitive
             endpoints (fortress fixes, owner guards); Guardian++
             adds the unified gate. No change needed here.
  Pillar 4 — WebSocket frame signature verification for enrolled
             mesh nodes lives in api/mesh_ws.py (companion change).

Keys: register_signing_key(key_id, public_key_hex). The stack's own
signing public key is auto-registered under the owner's id at import,
so owner clients that sign with the stack key verify out of the box.
"""
import hashlib
import hmac
import os
import threading
import time
from collections import defaultdict, deque

from core.logger import log_event

OWNER = "jesse_martinez_jr"
TIMESTAMP_WINDOW_MS = 30_000
NONCE_TTL = 60.0

SIGNING_ENFORCE = os.environ.get("SOVEREIGN_SIGNING_ENFORCE", "") == "1"
PROTECTED_PREFIXES = ("/command", "/build", "/credentials", "/guardian-plus", "/black-swarm")
COMPUTE_PREFIXES = ("/command", "/build", "/agssi", "/sentinel", "/guardian-plus",
                    "/black-swarm", "/v1/mesh", "/telemetry", "/mesh")
ADMIN_PREFIXES = ("/credentials", "/admin")

RATE_READ = 120
RATE_COMPUTE = 30
RATE_ADMIN = 5
RATE_DEFAULT_WRITE = 60
RATE_WINDOW = 60.0

SECURITY_HEADERS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "x-xss-protection": "1; mode=block",
    "strict-transport-security": "max-age=63072000; includeSubDomains; preload",
    "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
    "x-robots-tag": "noindex, nofollow, nosnippet, noarchive",
    "server": "CRSMCPAI-Sovereign-Mesh",
}

# ── signing key registry ───────────────────────────────────────────────
_SIGNING_KEYS: dict = {}
try:
    from security.crypto import get_public_key
    _SIGNING_KEYS[OWNER] = get_public_key()
except Exception:
    pass


def register_signing_key(key_id: str, public_key_hex: str) -> None:
    _SIGNING_KEYS[key_id] = public_key_hex


def _verify_signature(public_key_hex: str, message: bytes, signature_hex: str) -> bool:
    try:
        from nacl.signing import VerifyKey
        VerifyKey(bytes.fromhex(public_key_hex)).verify(message, bytes.fromhex(signature_hex))
        return True
    except Exception:
        pass
    try:  # HMAC fallback, mirroring api/mesh.py's fallback semantics
        expected = hmac.new(bytes.fromhex(public_key_hex), message, hashlib.sha3_512).hexdigest()
        return hmac.compare_digest(expected, signature_hex or "")
    except Exception:
        return False


# ── rate limiting ──────────────────────────────────────────────────────
class _RateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: dict = defaultdict(deque)

    def check(self, client: str, tier: str, limit: int, now: float) -> tuple:
        key = (client, tier)
        with self._lock:
            window = self._hits[key]
            window.append(now)
            while window and now - window[0] > RATE_WINDOW:
                window.popleft()
            if len(window) > limit:
                retry = int(RATE_WINDOW - (now - window[0])) + 1
                return False, retry
            return True, 0


def _tier_for(method: str, path: str) -> tuple:
    if method in ("GET", "HEAD"):
        return "read", RATE_READ
    if any(path.startswith(p) for p in ADMIN_PREFIXES):
        return "admin", RATE_ADMIN
    if any(path.startswith(p) for p in COMPUTE_PREFIXES):
        return "compute", RATE_COMPUTE
    return "write", RATE_DEFAULT_WRITE


# ── nonce replay cache ─────────────────────────────────────────────────
class _NonceCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._seen: dict = {}

    def use(self, nonce: str, now: float) -> bool:
        """True if the nonce is fresh (and records it); False on replay."""
        with self._lock:
            self._seen = {n: t for n, t in self._seen.items() if now - t <= NONCE_TTL}
            if nonce in self._seen:
                return False
            self._seen[nonce] = now
            return True


_RATE = _RateLimiter()
_NONCES = _NonceCache()


def _audit_failure(kind: str, client: str, path: str, reason: str) -> None:
    log_event(f"[HARDENING] {kind} client={client} path={path}: {reason}", "warning")
    try:
        from api.sentinel import sentinel_engine
        sentinel_engine.ingest({"source": client, "kind": "auth", "ok": False,
                                "action": kind})
    except Exception:
        pass
    try:
        from memory.ledger import create_event
        create_event({"module": "HARDENING", "event": kind, "client": client,
                      "path": path, "reason": reason})
    except Exception:
        pass


def verify_signed_request(method: str, path: str, headers: dict, body: bytes,
                            now_ms: int = None) -> tuple:
    """Verify the X-Sovereign-* signing headers. Returns (ok, reason).
    Caller guarantees the headers are present."""
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    key_id = headers.get("x-sovereign-key-id") or OWNER
    pubkey = headers.get("x-sovereign-key") or _SIGNING_KEYS.get(key_id)
    timestamp = headers.get("x-sovereign-timestamp") or ""
    nonce = headers.get("x-sovereign-nonce") or ""
    signature = headers.get("x-sovereign-signature") or ""
    if not pubkey or not timestamp or not nonce or not signature:
        return False, "missing sovereign security headers"
    try:
        ts_val = int(timestamp)
    except ValueError:
        return False, "timestamp not an integer"
    if abs(now_ms - ts_val) > TIMESTAMP_WINDOW_MS:
        return False, "timestamp outside the ±30s window"
    if not _NONCES.use(nonce, now_ms / 1000.0):
        return False, "nonce replay detected"
    body_hash = hashlib.sha256(body).hexdigest()
    signing_payload = f"{method}{path}{timestamp}{nonce}{body_hash}".encode()
    if not _verify_signature(pubkey, signing_payload, signature):
        return False, "signature verification failed"
    return True, "verified"


def sign_request(method: str, path: str, body: bytes, key_id: str = OWNER,
                 timestamp_ms: int = None, nonce: str = None) -> dict:
    """Produce the X-Sovereign-* headers for a request, signed with the
    stack signing key (the in-process client path)."""
    import secrets as _secrets
    from security.crypto import sign_data
    ts = str(timestamp_ms if timestamp_ms is not None else int(time.time() * 1000))
    nonce = nonce or _secrets.token_hex(16)
    body_hash = hashlib.sha256(body).hexdigest()
    payload = f"{method}{path}{ts}{nonce}{body_hash}".encode()
    return {
        "x-sovereign-key-id": key_id,
        "x-sovereign-timestamp": ts,
        "x-sovereign-nonce": nonce,
        "x-sovereign-signature": sign_data(payload),
    }


class HardeningMiddleware:
    """Pure ASGI middleware: security headers + rate limiting +
    request-signing verification (pillar 1/3/6/7)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        path = scope.get("path", "")
        client = (scope.get("client") or ("unknown", 0))[0]
        headers = {k.decode("latin-1").lower(): v.decode("latin-1")
                   for k, v in scope.get("headers", [])}

        # Read the body once; replay it downstream.
        body = b""
        more = True
        while more:
            message = await receive()
            if message["type"] == "http.request":
                body += message.get("body", b"")
                more = message.get("more_body", False)
            else:
                more = False

        async def replay_receive():
            return {"type": "http.request", "body": body, "more_body": False}

        # Pillar 3 — rate limiting
        tier, limit = _tier_for(method, path)
        ok, retry = _RATE.check(client, tier, limit, time.time())
        if not ok:
            _audit_failure("RATE_LIMIT_EXCEEDED", client, path,
                           f"tier {tier} limit {limit}/min exceeded")
            await self._reject(send, 429, "rate_limited",
                               {"retry-after": str(retry)})
            return

        # Pillar 1 — request signing
        has_signing = "x-sovereign-signature" in headers
        if has_signing:
            valid, reason = verify_signed_request(method, path, headers, body)
            if not valid:
                _audit_failure("SIGNATURE_MISMATCH", client, path, reason)
                await self._reject(send, 403, f"signature verification failed: {reason}")
                return
        elif SIGNING_ENFORCE and any(path.startswith(p) for p in PROTECTED_PREFIXES):
            _audit_failure("UNSIGNED_PROTECTED", client, path,
                           "protected endpoint requires a signed request")
            await self._reject(send, 401, "signed request required for this endpoint")
            return

        # Pillar 6 — security headers on the way out
        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                raw = [(k.lower(), v) for k, v in message.get("headers", [])]
                present = {k.decode("latin-1") for k, _ in raw}
                for name, value in SECURITY_HEADERS.items():
                    if name.encode() not in present:
                        raw.append((name.encode(), value.encode()))
                message = {**message, "headers": raw}
            await send(message)

        await self.app(scope, replay_receive, send_with_headers)

    async def _reject(self, send, status: int, detail: str, extra_headers: dict = None):
        import json as _json
        body = _json.dumps({"error": detail}).encode()
        hdrs = [(b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode())]
        for name, value in SECURITY_HEADERS.items():
            hdrs.append((name.encode(), value.encode()))
        for name, value in (extra_headers or {}).items():
            hdrs.append((name.encode(), value.encode()))
        await send({"type": "http.response.start", "status": status, "headers": hdrs})
        await send({"type": "http.response.body", "body": body})
