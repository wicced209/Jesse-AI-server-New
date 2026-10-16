"""
test_mesh.py — end-to-end exercise of api/mesh.py.

Flow: enroll -> confirm -> telemetry -> heartbeat -> directive -> ack -> status,
plus negative tests (bad signature, replayed nonce, stale timestamp, revoked node).
Run:  ~/workspace/mesh_venv/bin/python test_mesh.py
"""
import json
import sys
import time
import uuid

sys.path.insert(0, "/home/hatch/workspace/repo_inspect")

from fastapi import FastAPI
from fastapi.testclient import TestClient
from nacl.signing import SigningKey

from api.mesh import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))


def canonical(d):
    return json.dumps(d, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign(sk, msg_bytes):
    return sk.sign(msg_bytes).signature.hex()


# --- test node identity -----------------------------------------------------
sk = SigningKey.generate()
vk_hex = sk.verify_key.encode().hex()
node_uuid = "test-node-" + uuid.uuid4().hex[:8]

# 1. enroll
r = client.post("/v1/mesh/enroll", json={
    "node_uuid": node_uuid, "public_key": vk_hex,
    "capabilities": ["telemetry", "directive_exec"]})
check("1 enroll returns challenge", r.status_code == 200 and "challenge" in r.json())
challenge = r.json()["challenge"]

# 2. confirm with real signature
r = client.post("/v1/mesh/enroll/confirm", json={
    "node_uuid": node_uuid, "signature": sign(sk, challenge.encode())})
check("2 enroll/confirm activates node",
      r.status_code == 200 and r.json().get("status") == "active", r.text[:120])

# 2b. confirm with WRONG signature must fail
sk2 = SigningKey.generate()
r = client.post("/v1/mesh/enroll", json={
    "node_uuid": node_uuid + "-bad", "public_key": sk2.verify_key.encode().hex(),
    "capabilities": []})
bad_chal = r.json()["challenge"]
r = client.post("/v1/mesh/enroll/confirm", json={
    "node_uuid": node_uuid + "-bad", "signature": sign(sk, bad_chal.encode())})
check("2b wrong signature rejected", r.status_code == 401, r.text[:120])

# 3. telemetry with real signature
ts = time.time()
nonce = uuid.uuid4().hex
payload = {"cpu": 0.42, "mem_mb": 512, "event": "heartbeat_extended"}
body = {"node_uuid": node_uuid, "timestamp": ts, "nonce": nonce, "payload": payload}
sig = sign(sk, canonical({"node_uuid": node_uuid, "timestamp": ts, "nonce": nonce, "payload": payload}))
r = client.post("/v1/mesh/telemetry", json={**body, "signature": sig})
check("3 telemetry accepted", r.status_code == 200 and r.json().get("accepted") is True, r.text[:120])
receipt = r.json().get("receipt_id")

# 3b. replay same nonce must be rejected
r = client.post("/v1/mesh/telemetry", json={**body, "signature": sig})
check("3b replayed nonce rejected", r.status_code == 409, r.text[:120])

# 3c. tampered payload must fail signature check
nonce3 = uuid.uuid4().hex
ts3 = time.time()
sig3 = sign(sk, canonical({"node_uuid": node_uuid, "timestamp": ts3, "nonce": nonce3,
                           "payload": {"cpu": 0.1}}))
r = client.post("/v1/mesh/telemetry", json={
    "node_uuid": node_uuid, "timestamp": ts3, "nonce": nonce3,
    "payload": {"cpu": 0.99}, "signature": sig3})  # payload differs from signed bytes
check("3c tampered payload rejected", r.status_code == 401, r.text[:120])

# 3d. stale timestamp must fail
nonce4 = uuid.uuid4().hex
old_ts = time.time() - 3600
sig4 = sign(sk, canonical({"node_uuid": node_uuid, "timestamp": old_ts, "nonce": nonce4,
                           "payload": payload}))
r = client.post("/v1/mesh/telemetry", json={
    "node_uuid": node_uuid, "timestamp": old_ts, "nonce": nonce4,
    "payload": payload, "signature": sig4})
check("3d stale timestamp rejected", r.status_code == 401, r.text[:120])

# 4. heartbeat (no directives queued yet)
ts = time.time()
r = client.post("/v1/mesh/heartbeat", json={
    "node_uuid": node_uuid, "timestamp": ts,
    "signature": sign(sk, canonical({"node_uuid": node_uuid, "timestamp": ts}))})
check("4 heartbeat ok, 0 queued",
      r.status_code == 200 and r.json().get("count") == 0, r.text[:120])

# 5. create directive targeting the node
r = client.post("/v1/mesh/directives", json={
    "command": "collect_telemetry", "target_nodes": [node_uuid], "priority": "high"})
check("5 directive created", r.status_code == 200 and "directive_id" in r.json(), r.text[:120])
did = r.json()["directive_id"]

# 5b. directive detail shows QUEUED
r = client.get(f"/v1/mesh/directives/{did}")
check("5b directive detail QUEUED",
      r.status_code == 200 and r.json()["targets"][node_uuid]["state"] == "QUEUED",
      r.text[:120])

# 6. heartbeat now pulls the directive (pull-based delivery)
ts = time.time()
r = client.post("/v1/mesh/heartbeat", json={
    "node_uuid": node_uuid, "timestamp": ts,
    "signature": sign(sk, canonical({"node_uuid": node_uuid, "timestamp": ts}))})
qd = r.json().get("queued_directives", [])
check("6 heartbeat pulls 1 directive",
      r.status_code == 200 and len(qd) == 1 and qd[0]["directive_id"] == did, r.text[:160])

# 6b. second heartbeat gets nothing (already delivered)
ts = time.time()
r = client.post("/v1/mesh/heartbeat", json={
    "node_uuid": node_uuid, "timestamp": ts,
    "signature": sign(sk, canonical({"node_uuid": node_uuid, "timestamp": ts}))})
check("6b no duplicate delivery", r.status_code == 200 and r.json().get("count") == 0, r.text[:120])

# 7. ack with signed result
result = {"ok": True, "telemetry_sent": 42}
r = client.post(f"/v1/mesh/directives/{did}/ack", json={
    "node_uuid": node_uuid, "result": result,
    "signature": sign(sk, canonical({"directive_id": did, "node_uuid": node_uuid, "result": result}))})
check("7 ack accepted", r.status_code == 200 and r.json().get("state") == "ACKED", r.text[:120])

# 7b. ack with bad signature rejected
r = client.post(f"/v1/mesh/directives/{did}/ack", json={
    "node_uuid": node_uuid, "result": result, "signature": "00" * 64})
check("7b bad ack signature rejected", r.status_code == 401, r.text[:120])

# 8. status reflects real state
r = client.get("/v1/mesh/status")
s = r.json()
check("8 status counts correct",
      r.status_code == 200 and s["node_count"] >= 1 and s["active_nodes"] >= 1
      and s["telemetry_count"] >= 1 and s["acked_directives"] >= 1,
      r.text[:200])

# 9. nodes list
r = client.get("/v1/mesh/nodes")
check("9 nodes listed", r.status_code == 200 and r.json()["count"] >= 1, r.text[:120])

# 10. revoke node, then telemetry must be refused
r = client.delete(f"/v1/mesh/nodes/{node_uuid}")
check("10 node revoked", r.status_code == 200 and r.json()["status"] == "REVOKED", r.text[:120])
ts = time.time()
nonce5 = uuid.uuid4().hex
r = client.post("/v1/mesh/telemetry", json={
    "node_uuid": node_uuid, "timestamp": ts, "nonce": nonce5, "payload": payload,
    "signature": sign(sk, canonical({"node_uuid": node_uuid, "timestamp": ts,
                                     "nonce": nonce5, "payload": payload}))})
check("10b revoked node telemetry refused", r.status_code == 403, r.text[:120])

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
