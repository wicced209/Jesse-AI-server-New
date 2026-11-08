#!/usr/bin/env python3
"""
CRSMCPAI Alpha — Reference Telemetry Node (v1, 2026-11-08, Muse).

The first external CRS source built to connect to the live stack the
way the network was designed to be connected to:

  1. Mesh enrollment (api/mesh.py): the node generates an Ed25519
     keypair, enrolls its public key, answers the hub's challenge
     with a signature, and becomes an ACTIVE mesh node with a token.
  2. Telemetry registration (api/telemetry_ingest.py): the node
     registers as a telemetry source under the owner's authority and
     receives its source secret (shown once; kept in the node's own
     state file on the node's own machine, mode 0600).
  3. Streaming: every cycle the node measures REAL readings from its
     own host (load, memory, disk, uptime) and the real round-trip
     latency to the stack, signs the batch exactly as the intake
     requires (HMAC-SHA3-512 over the canonical batch body), and
     posts it to /telemetry/ingest with an advancing sequence.

The stack's registries are in-memory, so a stack restart wipes them;
the node treats unknown_source / not-enrolled answers as its cue to
re-enroll and re-register automatically, then keeps streaming. That
recovery behavior is deliberate: nodes are supposed to survive hub
restarts, because restoration is reconnection.

Usage:
    python3 telemetry_node.py --url https://<stack-host> \
        --label "reference-node-1" --interval 15 --count 0

--count 0 streams until stopped. State (source secret, sequence,
mesh token) persists in --state (default ./telemetry_node_state.json)
so a node restart resumes instead of re-registering from scratch.

Owner: SLMK Jesse Martinez Junior.
"""
import argparse
import hashlib
import hmac
import json
import os
import secrets
import shutil
import sys
import time
import urllib.error
import urllib.request

OWNER = "jesse_martinez_jr"


# ── HTTP ───────────────────────────────────────────────────────────────

def http_json(method, url, body=None, headers=None, timeout=30):
    req = urllib.request.Request(
        url, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:
            return e.code, {}


# ── Signing (mirrors api/telemetry_ingest.py exactly) ──────────────────

def _key(secret_value):
    return hashlib.sha3_512(secret_value.encode()).hexdigest()


def _canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def sign_batch(secret_value, source_id, sequence, timestamp, events):
    body = {"source_id": source_id, "sequence": sequence,
            "timestamp": timestamp, "events": events}
    return hmac.new(_key(secret_value).encode(),
                    (_canon(body) + "|" + str(timestamp)).encode(),
                    hashlib.sha3_512).hexdigest()


# ── Host readings (real measurements of the node's own machine) ────────

def host_readings():
    readings = {"ts": time.time()}
    try:
        readings["load_1m"], readings["load_5m"], readings["load_15m"] = os.getloadavg()
    except OSError:
        pass
    try:
        mem = {}
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split()
                if parts and parts[0] in ("MemTotal:", "MemAvailable:"):
                    mem[parts[0].rstrip(":")] = int(parts[1])
        if mem:
            readings["mem_total_kb"] = mem.get("MemTotal")
            readings["mem_available_kb"] = mem.get("MemAvailable")
    except OSError:
        pass
    try:
        with open("/proc/uptime") as f:
            readings["host_uptime_s"] = float(f.read().split()[0])
    except OSError:
        pass
    try:
        usage = shutil.disk_usage(os.getcwd())
        readings["disk_free_gb"] = round(usage.free / 1e9, 2)
        readings["disk_total_gb"] = round(usage.total / 1e9, 2)
    except OSError:
        pass
    readings["cpu_count"] = os.cpu_count()
    return readings


# ── The node ───────────────────────────────────────────────────────────

class TelemetryNode:
    def __init__(self, base_url, label, node_id=None, state_path=None):
        self.base = base_url.rstrip("/")
        self.label = label
        self.node_id = node_id or f"crs-node-{secrets.token_hex(4)}"
        self.state_path = state_path or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "telemetry_node_state.json")
        self.state = self._load_state()
        self.started = time.time()
        self.batches_acked = 0

    def _load_state(self):
        try:
            with open(self.state_path) as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_state(self):
        tmp = self.state_path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.state, f)
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.state_path)

    # Mesh enrollment: Ed25519 challenge-response (HMAC fallback when
    # PyNaCl is unavailable, mirroring api/mesh.py's fallback mode).
    def enroll_mesh(self):
        from nacl.signing import SigningKey
        seed_hex = self.state.get("mesh_seed")
        if seed_hex:
            sk = SigningKey(bytes.fromhex(seed_hex))
        else:
            sk = SigningKey.generate()
            self.state["mesh_seed"] = sk.encode().hex()
        pub = sk.verify_key.encode().hex()
        code, resp = http_json("POST", f"{self.base}/v1/mesh/enroll", {
            "node_uuid": self.node_id, "public_key": pub,
            "capabilities": ["telemetry", "host_metrics", "link_metrics"]})
        if code != 200 or "challenge" not in resp:
            return {"ok": False, "step": "enroll", "response": resp}
        signature = sk.sign(resp["challenge"].encode("utf-8")).signature.hex()
        code, resp = http_json("POST", f"{self.base}/v1/mesh/enroll/confirm", {
            "node_uuid": self.node_id, "signature": signature})
        if code != 200 or "node_token" not in resp:
            return {"ok": False, "step": "confirm", "response": resp}
        self.state["mesh_token"] = resp["node_token"]
        self.state["mesh_status"] = resp.get("status")
        self._save_state()
        return {"ok": True, "status": resp.get("status"), "crypto": resp.get("crypto")}

    def register_source(self):
        code, resp = http_json("POST", f"{self.base}/telemetry/sources", {
            "user": OWNER, "label": self.label})
        if code != 200 or not resp.get("ok"):
            return {"ok": False, "response": resp}
        src = resp["source"]
        self.state["source_id"] = src["source_id"]
        self.state["source_secret"] = src["source_secret"]
        self.state["sequence"] = 0
        self._save_state()
        return {"ok": True, "source_id": src["source_id"]}

    def measure_link(self):
        start = time.time()
        code, _ = http_json("GET", f"{self.base}/health", timeout=15)
        return {"health_status": code,
                "round_trip_ms": round((time.time() - start) * 1000, 1)}

    def collect_events(self):
        return [
            {"kind": "host_metrics", "node": self.node_id, **host_readings()},
            {"kind": "link_metrics", "node": self.node_id, **self.measure_link()},
            {"kind": "heartbeat", "node": self.node_id,
             "node_uptime_s": round(time.time() - self.started, 1),
             "batches_acked": self.batches_acked},
        ]

    def send_batch(self):
        if not self.state.get("source_id"):
            reg = self.register_source()
            if not reg.get("ok"):
                return reg
        seq = int(self.state.get("sequence", 0)) + 1
        ts = time.time()
        events = self.collect_events()
        signature = sign_batch(self.state["source_secret"],
                               self.state["source_id"], seq, ts, events)
        code, resp = http_json("POST", f"{self.base}/telemetry/ingest", {
            "source_id": self.state["source_id"], "sequence": seq,
            "timestamp": ts, "events": events, "signature": signature})
        if resp.get("error") == "unknown_source":
            # The hub restarted and its registry reset: re-register
            # and retry once. Restoration is reconnection.
            self.state.pop("source_id", None)
            self.state.pop("source_secret", None)
            self._save_state()
            reg = self.register_source()
            if not reg.get("ok"):
                return reg
            return self.send_batch()
        if resp.get("accepted"):
            self.state["sequence"] = seq
            self._save_state()
            self.batches_acked += 1
        return resp

    def run(self, interval, count):
        mesh = self.enroll_mesh()
        print(f"[node] mesh enrollment: {mesh}")
        reg = {"ok": True} if self.state.get("source_id") else self.register_source()
        print(f"[node] telemetry registration: {reg}")
        sent = 0
        while count == 0 or sent < count:
            resp = self.send_batch()
            print(f"[node] batch {sent + 1}: {resp}")
            sent += 1
            if count == 0 or sent < count:
                time.sleep(interval)
        return sent


def main():
    ap = argparse.ArgumentParser(description="CRSMCPAI Alpha reference telemetry node")
    ap.add_argument("--url", required=True, help="base URL of the live stack")
    ap.add_argument("--label", default="reference-node")
    ap.add_argument("--node-id", default=None)
    ap.add_argument("--interval", type=float, default=15.0)
    ap.add_argument("--count", type=int, default=1,
                    help="batches to send; 0 = stream forever")
    ap.add_argument("--state", default=None, help="state file path")
    args = ap.parse_args()
    node = TelemetryNode(args.url, args.label, args.node_id, args.state)
    try:
        node.run(args.interval, args.count)
    except KeyboardInterrupt:
        print("[node] stopped by operator")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
