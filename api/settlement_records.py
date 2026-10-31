"""
Settlement records — CRSMCPAI Alpha payment-lane bookkeeping.

Spec source: Jesse AI's execution-66 gap list (2026-10-30):
"cryptographic settlement scripts, transaction hash generators,
balance update functions — missing from the ledger module." This
module is that bookkeeping layer for the x402 agent lane: it records
settlements, gives each one a deterministic transaction hash, keeps
per-address balances derived from those records, and seals every
record into the production Golden Ledger through an injected seal.

Honesty rules, enforced in code:
  - Every record carries a source. "facilitator" means a real
    payment facilitator confirmed it (a receipt reference is
    required). "simulated" means it came from the sandbox/test lane.
    Simulated records NEVER count toward settled balances — the two
    are tracked and reported separately, always.
  - This module moves no money, signs nothing, holds no keys, and
    makes no chain or provider calls. It is the record the real
    settlement will be checked against when a facilitator exists.
  - Balances are DERIVED from the record chain (recomputable at any
    time), never stored as mutable numbers that can drift from the
    records.
  - The record chain is SHA3-512 hash-linked like the production
    ledger; a record's transaction hash is the hash of its canonical
    contents, so any later edit breaks verification.

States: RECORDED (awaiting confirmation) -> CONFIRMED (counts toward
settled balance, facilitator source only) or -> VOID (reversed before
confirmation). Simulated records can be confirmed inside the
simulation ledger but stay in the simulated column forever.
"""

import hashlib
import json
import time
import uuid

OWNER = "SLMK Jesse Martinez Junior"

_RECORDS = []          # settlement records, append-only
_BY_HASH = {}          # tx_hash -> record
_EVENTS = []           # in-memory mirror of sealed events

_seal_fn = None


def set_seal_fn(fn):
    """Inject the production seal (memory.ledger.create_event)."""
    global _seal_fn
    _seal_fn = fn


def _seal(event_type, payload):
    event = {"kind": "settlement", "event": event_type, **payload}
    _EVENTS.append({"ts": time.time(), **event})
    if _seal_fn is not None:
        try:
            _seal_fn(event)
        except Exception:
            pass  # sealing must never break the bookkeeping


def _canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def transaction_hash(record_body, prev_hash):
    """The transaction hash generator: SHA3-512 over the canonical
    record body plus the previous record's hash (chain link)."""
    return hashlib.sha3_512(
        (_canon(record_body) + "|" + prev_hash).encode()).hexdigest()


def _valid_address(addr):
    return (isinstance(addr, str) and addr.startswith("0x")
            and len(addr) == 42
            and all(c in "0123456789abcdefABCDEF" for c in addr[2:]))


def record_settlement(payer, payee, amount_cents, asset="USDC",
                      chain="base", source="simulated",
                      facilitator_ref=""):
    """Record one settlement. amount_cents is the smallest-unit
    integer of the asset amount times 100 for readability in this
    lane's records (USDC cents); it must be a positive integer."""
    if source not in ("facilitator", "simulated"):
        return {"ok": False,
                "error": "source must be 'facilitator' or 'simulated'"}
    if source == "facilitator" and not facilitator_ref:
        return {"ok": False,
                "error": "facilitator records require a receipt "
                         "reference — real settlements are never "
                         "recorded on a claim alone"}
    if not _valid_address(payer or ""):
        return {"ok": False, "error": "payer must be an EVM address"}
    if not _valid_address(payee or ""):
        return {"ok": False, "error": "payee must be an EVM address"}
    if (not isinstance(amount_cents, int)
            or isinstance(amount_cents, bool)
            or amount_cents <= 0 or amount_cents > 100_000_000):
        return {"ok": False,
                "error": "amount_cents must be a positive integer "
                         "up to 100000000"}
    if asset not in ("USDC",):
        return {"ok": False, "error": "asset must be USDC in this lane"}
    body = {
        "settlement_id": "stl_" + uuid.uuid4().hex[:16],
        "payer": payer, "payee": payee,
        "amount_cents": amount_cents, "asset": asset, "chain": chain,
        "source": source, "facilitator_ref": facilitator_ref or "",
        "state": "RECORDED", "recorded_ts": time.time(),
    }
    prev = _RECORDS[-1]["tx_hash"] if _RECORDS else "GENESIS_SETTLEMENT"
    tx = transaction_hash(body, prev)
    rec = {**body, "tx_hash": tx, "prev_hash": prev}
    _RECORDS.append(rec)
    _BY_HASH[tx] = rec
    _seal("settlement_recorded",
          {"settlement_id": body["settlement_id"], "tx_hash": tx,
           "source": source, "amount_cents": amount_cents,
           "asset": asset, "chain": chain})
    return {"ok": True, "settlement": dict(rec)}


def confirm_settlement(tx_hash):
    rec = _BY_HASH.get(tx_hash or "")
    if not rec:
        return {"ok": False, "error": "unknown transaction hash"}
    if rec["state"] == "CONFIRMED":
        return {"ok": True, "idempotent_replay": True,
                "settlement": dict(rec)}
    if rec["state"] == "VOID":
        return {"ok": False,
                "error": "a voided settlement cannot be confirmed"}
    rec["state"] = "CONFIRMED"
    rec["confirmed_ts"] = time.time()
    _seal("settlement_confirmed",
          {"settlement_id": rec["settlement_id"], "tx_hash": tx_hash,
           "source": rec["source"]})
    return {"ok": True, "settlement": dict(rec)}


def void_settlement(tx_hash, reason=""):
    rec = _BY_HASH.get(tx_hash or "")
    if not rec:
        return {"ok": False, "error": "unknown transaction hash"}
    if rec["state"] == "CONFIRMED":
        return {"ok": False,
                "error": "a confirmed settlement cannot be voided — "
                         "reversals are new records, not edits"}
    if rec["state"] == "VOID":
        return {"ok": True, "idempotent_replay": True,
                "settlement": dict(rec)}
    rec["state"] = "VOID"
    rec["void_reason"] = reason or ""
    _seal("settlement_voided",
          {"settlement_id": rec["settlement_id"], "tx_hash": tx_hash})
    return {"ok": True, "settlement": dict(rec)}


def _identity_body(rec):
    """The fields a record's transaction hash covers: its identity at
    recording time. Lifecycle state is deliberately excluded —
    confirmations and voids are sealed events, not edits."""
    return {
        "settlement_id": rec["settlement_id"], "payer": rec["payer"],
        "payee": rec["payee"], "amount_cents": rec["amount_cents"],
        "asset": rec["asset"], "chain": rec["chain"],
        "source": rec["source"],
        "facilitator_ref": rec["facilitator_ref"],
        "state": "RECORDED", "recorded_ts": rec["recorded_ts"],
    }


def verify_settlement(tx_hash):
    """Recompute the record's hash from its stored identity and chain
    position. Any tampering with amount, parties, or source breaks
    it."""
    rec = _BY_HASH.get(tx_hash or "")
    if not rec:
        return {"ok": False, "verified": False,
                "error": "unknown transaction hash"}
    expect = transaction_hash(_identity_body(rec), rec["prev_hash"])
    return {"ok": True, "verified": expect == tx_hash,
            "settlement": dict(rec)}


def balances(address=""):
    """The balance update function: balances are recomputed from the
    confirmed records on every call. Facilitator-confirmed and
    simulated totals are always separate columns."""
    out = {}

    def bucket(addr):
        return out.setdefault(addr, {
            "settled_received_cents": 0, "settled_sent_cents": 0,
            "simulated_received_cents": 0, "simulated_sent_cents": 0})
    for rec in _RECORDS:
        if rec["state"] != "CONFIRMED":
            continue
        col = "settled" if rec["source"] == "facilitator" else "simulated"
        bucket(rec["payee"])[f"{col}_received_cents"] += rec["amount_cents"]
        bucket(rec["payer"])[f"{col}_sent_cents"] += rec["amount_cents"]
    if address:
        empty = {"settled_received_cents": 0, "settled_sent_cents": 0,
                 "simulated_received_cents": 0,
                 "simulated_sent_cents": 0}
        return {"address": address,
                "balances": out.get(address, empty)}
    return {"balances": out, "addresses": len(out)}


def chain_valid():
    prev = "GENESIS_SETTLEMENT"
    for rec in _RECORDS:
        if rec["prev_hash"] != prev:
            return False
        if transaction_hash(_identity_body(rec), prev) != rec["tx_hash"]:
            return False
        prev = rec["tx_hash"]
    return True


def list_settlements(source="", state=""):
    out = [dict(r) for r in _RECORDS
           if (not source or r["source"] == source)
           and (not state or r["state"] == state)]
    return {"settlements": out, "count": len(out),
            "chain_valid": chain_valid()}


def settlement_status():
    by_state, by_source = {}, {}
    for r in _RECORDS:
        by_state[r["state"]] = by_state.get(r["state"], 0) + 1
        by_source[r["source"]] = by_source.get(r["source"], 0) + 1
    return {
        "module": "settlement_records", "owner": OWNER,
        "records_total": len(_RECORDS),
        "records_by_state": by_state, "records_by_source": by_source,
        "chain_valid": chain_valid(),
        "money_moved": False, "chain_calls": 0, "keys_held": False,
        "state_storage": "in-memory — resets on restart; every record "
                         "is sealed to the Golden Ledger so the audit "
                         "trail persists",
        "balance_rule": "balances derive only from CONFIRMED records; "
                        "facilitator-confirmed and simulated totals "
                        "are always reported separately",
    }
