#!/usr/bin/env python3
"""
CRSMCPAI Alpha — Archive Ingester (2026-11-08, Muse).

Feeds file-held historical records into the live stack as sealed,
source-tagged telemetry, per the agreed archive-ingestion framing:
register one telemetry source per legacy archive line, verify the
archive's chain locally, and ingest a truthful summary batch
through the guarded intake — so the live telemetry picture carries
the historical flow with its origin named, and never presents an
archive's contents as live traffic.

What gets verified before anything is sent:
  * every block's hash is recomputed from its canonical core
    (index, ts, owner, payload, prev_hash) with SHA3-512 — the same
    formula the ledger uses;
  * the prev_hash linkage is walked end to end;
  * the genesis anchor is checked against the stack's GENESIS
    constant.
The summary event states the verification outcome exactly: fully
verified, or the precise failure. A broken archive is reported,
never papered over.

Events ingested (one signed batch):
  * archive_summary — tag, file, block count, era span (first and
    last block timestamps), genesis anchor match, hash and link
    verification results, head hash;
  * archive_kind_count — the payload event/kind histogram, split
    into a few events so the historical mix stays queryable.

Usage:
  python3 nodes/archive_ingest.py --url https://hub.example \
      --file ledger_full.json --tag railway-era-ledger-2026-10-31 \
      --user jesse_martinez_jr

Owner: SLMK Jesse Martinez Junior.
"""
import argparse
import collections
import hashlib
import importlib.util
import json
import pathlib
import time

GENESIS = "92038cafccc7192535bd475cca985d03000d89962b8dc96f6664081663559b1b"

_HERE = pathlib.Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "telemetry_node", _HERE / "telemetry_node.py")
_node = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_node)
http_json = _node.http_json
sign_batch = _node.sign_batch


def load_blocks(path: str) -> list[dict]:
    data = json.loads(pathlib.Path(path).read_text())
    if isinstance(data, dict) and "blocks" in data:
        return data["blocks"]
    if isinstance(data, list):
        return data
    raise ValueError("unrecognized archive shape: expected a block list "
                     "or an object with a 'blocks' list")


def verify_chain(blocks: list[dict]) -> dict:
    """Recompute every hash and walk the linkage. Returns the exact
    outcome; indexes are reported, never hidden."""
    hash_failures = []
    link_failures = []
    for i, block in enumerate(blocks):
        core = {"index": int(block["index"]), "ts": float(block["ts"]),
                "owner": block["owner"], "payload": block["payload"],
                "prev_hash": block["prev_hash"]}
        digest = hashlib.sha3_512(
            json.dumps(core, sort_keys=True).encode()).hexdigest()
        if digest != block["block_hash"]:
            hash_failures.append(i)
        expected_prev = GENESIS if i == 0 else blocks[i - 1]["block_hash"]
        if block["prev_hash"] != expected_prev:
            link_failures.append(i)
    return {"blocks": len(blocks),
            "hash_verified": not hash_failures,
            "hash_failures": hash_failures[:10],
            "links_verified": not link_failures,
            "link_failures": link_failures[:10],
            "genesis_anchor_ok": bool(blocks) and blocks[0]["prev_hash"] == GENESIS}


def summarize(blocks: list[dict], verification: dict, tag: str,
              filename: str) -> list[dict]:
    kinds: collections.Counter = collections.Counter()
    for block in blocks:
        payload = block.get("payload") or {}
        if isinstance(payload, dict):
            kinds[str(payload.get("event") or payload.get("kind")
                      or payload.get("system") or "other")] += 1
        else:
            kinds["non-dict payload"] += 1
    ts_values = [float(b["ts"]) for b in blocks]
    events = [{
        "kind": "archive_summary",
        "source_tag": tag,
        "archive_file": filename,
        "blocks": len(blocks),
        "era_start_ts": min(ts_values), "era_end_ts": max(ts_values),
        "head_hash": blocks[-1]["block_hash"],
        "verification": verification,
        "note": "historical archive summary — sealed and source-tagged; "
                "not live traffic",
    }]
    for kind_name, count in kinds.most_common(12):
        events.append({"kind": "archive_kind_count", "source_tag": tag,
                       "payload_kind": kind_name, "count": count})
    return events


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--file", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--user", default="jesse_martinez_jr")
    args = parser.parse_args()

    blocks = load_blocks(args.file)
    verification = verify_chain(blocks)
    print(f"[archive] {args.tag}: {len(blocks)} blocks | "
          f"hash_verified={verification['hash_verified']} "
          f"links_verified={verification['links_verified']} "
          f"genesis_ok={verification['genesis_anchor_ok']}")

    code, resp = http_json("POST", f"{args.url}/telemetry/sources",
                           {"user": args.user, "label": f"archive:{args.tag}"})
    source = (resp or {}).get("source") or {}
    if not source.get("source_id"):
        raise SystemExit(f"source registration failed: {resp}")
    source_id = source["source_id"]
    secret = source["source_secret"]

    events = summarize(blocks, verification, args.tag,
                       pathlib.Path(args.file).name)
    ts = time.time()
    signature = sign_batch(secret, source_id, 1, ts, events)
    code, resp = http_json("POST", f"{args.url}/telemetry/ingest", {
        "source_id": source_id, "sequence": 1, "timestamp": ts,
        "events": events, "signature": signature})
    print(f"[archive] ingest response: {resp}")
    if not (resp or {}).get("accepted"):
        raise SystemExit("ingest was not accepted")
    print(f"[archive] DONE — {len(events)} source-tagged events sealed "
          f"for {args.tag}")


if __name__ == "__main__":
    main()
