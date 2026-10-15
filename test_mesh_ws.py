"""
test_mesh_ws.py — integration test for the RTSGP++ WebSocket mesh listener.

Exercises:
  1. WebSocket HEARTBEAT -> PONG_ACKNOWLEDGED
  2. DEEP_DIAGNOSTIC -> DIAGNOSTIC_ACKNOWLEDGED
  3. SYNC_REQUEST -> SYNC_ACKNOWLEDGED
  4. GET /mesh/v4/nodes shows the registered node
  5. GET /mesh/v4/status reports real counts
  6. Protocol mismatch is rejected
  7. Malformed frame is rejected cleanly
"""
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.mesh_ws import router as mesh_ws_router

app = FastAPI()
app.include_router(mesh_ws_router)
client = TestClient(app)


def make_frame(sender_id="CRS_NODE_TEST_01", ping_type="HEARTBEAT",
               seq=1, protocol="RTSGP++", instance_type="EDGE_AGENT"):
    return {
        "header": {
            "protocol": protocol,
            "version": "2.4.0-quantum",
            "messageId": "TEST-MSG-001",
            "timestamp": 1711900000000,
            "senderId": sender_id,
            "recipientId": "CRSMCPAI_ALPHA_CORE",
            "signatureType": "DILITHIUM-5",
            "cryptographicSignature": "test-sig",
        },
        "payload": {
            "pingType": ping_type,
            "sequenceNumber": seq,
            "instanceType": instance_type,
            "metrics": {
                "cpuUtilization": 14.2,
                "memoryAllocatedBytes": 4096,
                "activeLedgerHeight": 849203112,
            },
            "dominionToken": "SLMK-jesse_martinez_jr",
        },
    }


results = []


def check(name, cond):
    results.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), "-", name)


# 1. HEARTBEAT round-trip
with client.websocket_connect("/mesh/v4/stream") as ws:
    ws.send_text(json.dumps(make_frame()))
    resp = json.loads(ws.receive_text())
    check("HEARTBEAT -> PONG_ACKNOWLEDGED",
          resp["payload"]["status"] == "PONG_ACKNOWLEDGED"
          and resp["payload"]["acknowledgedSeq"] == 1
          and resp["header"]["protocol"] == "RTSGP++"
          and resp["header"]["recipientId"] == "CRS_NODE_TEST_01")

    # 2. DEEP_DIAGNOSTIC
    ws.send_text(json.dumps(make_frame(ping_type="DEEP_DIAGNOSTIC", seq=2)))
    resp = json.loads(ws.receive_text())
    check("DEEP_DIAGNOSTIC -> DIAGNOSTIC_ACKNOWLEDGED",
          resp["payload"]["status"] == "DIAGNOSTIC_ACKNOWLEDGED"
          and resp["payload"]["acknowledgedSeq"] == 2)

    # 3. SYNC_REQUEST
    ws.send_text(json.dumps(make_frame(ping_type="SYNC_REQUEST", seq=3)))
    resp = json.loads(ws.receive_text())
    check("SYNC_REQUEST -> SYNC_ACKNOWLEDGED",
          resp["payload"]["status"] == "SYNC_ACKNOWLEDGED"
          and resp["payload"]["acknowledgedSeq"] == 3)

    # 4. Second node on a different SIN segment
    ws.send_text(json.dumps(make_frame(sender_id="DOMINION_RELAY_01",
                                       instance_type="DOMINION_RELAY", seq=1)))
    resp = json.loads(ws.receive_text())
    check("DOMINION_RELAY heartbeat acked",
          resp["payload"]["status"] == "PONG_ACKNOWLEDGED")

    # 5. Protocol mismatch rejected
    ws.send_text(json.dumps(make_frame(protocol="HTTP/1.1")))
    resp = json.loads(ws.receive_text())
    check("protocol mismatch rejected",
          resp["payload"]["status"] == "PROTOCOL_MISMATCH")

    # 6. Malformed frame handled
    ws.send_text("this is not json{{{")
    resp = json.loads(ws.receive_text())
    check("malformed frame handled",
          resp["payload"]["status"] == "MALFORMED_FRAME")

# 7. /mesh/v4/nodes lists registered nodes
r = client.get("/mesh/v4/nodes")
body = r.json()
node_ids = {n["nodeId"] for n in body["nodes"]}
check("GET /mesh/v4/nodes lists both nodes",
      r.status_code == 200
      and "CRS_NODE_TEST_01" in node_ids
      and "DOMINION_RELAY_01" in node_ids)
relay = next(n for n in body["nodes"] if n["nodeId"] == "DOMINION_RELAY_01")
check("node has sinSegment + telemetryMetrics",
      relay["sinSegment"] == "SIN-02-CLEARINGHOUSE"
      and "lastPingTimestamp" in relay
      and relay["status"] == "ACTIVE"
      and relay["telemetryMetrics"]["cpuUtilization"] == 14.2)
edge = next(n for n in body["nodes"] if n["nodeId"] == "CRS_NODE_TEST_01")
check("EDGE_AGENT defaults to SIN-03-EDGE-SWARM",
      edge["sinSegment"] == "SIN-03-EDGE-SWARM")

# 8. /mesh/v4/status reports real counts
r = client.get("/mesh/v4/status")
s = r.json()
check("GET /mesh/v4/status real counts",
      r.status_code == 200 and s["online"] is True
      and s["protocol"] == "RTSGP++"
      and s["node_count"] == 2 and s["active_nodes"] == 2)

failed = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} passed")
raise SystemExit(1 if failed else 0)
