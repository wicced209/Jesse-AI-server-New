"""
Sandbox transaction test environment — CRSMCPAI Alpha.

Spec source: Jesse AI's named build components (executions 66 and 67,
2026-10-30): a sandbox transaction test environment with test card
tokens, mock ledger records, and simulated payment payloads, built
inside the stack so the payment lane can be exercised end to end
BEFORE any live merchant account exists. The live payment gateway
itself stays blocked on external provider provisioning (accounts are
created openly with the owner); this module is the harness that
stands ready for it.

SANDBOX ONLY, by construction:
  - No real money moves. No network call to any payment provider is
    made anywhere in this module. No real card number is accepted:
    the API takes test TOKENS, and the only tokens that exist are the
    publicly documented industry test fixtures below.
  - Mock records live in this module's OWN SHA3-512 hash chain,
    genesis-labeled SANDBOX, using the same block discipline as the
    production Golden Ledger (memory/ledger.py). The production
    ledger is never written by this module.
  - The sandbox chain is in-memory: a restart resets it, which the
    status endpoint states plainly. A test harness that pretends to
    be permanent would be lying about what it is.
  - The webhook signing secret is a fixed, public TEST fixture (the
    same role Stripe's documented test secrets play). It protects
    nothing real; it exists so signature verification can be
    exercised deterministically.

Lifecycle: intent REQUIRES_CONFIRMATION -> confirm(token) ->
SUCCEEDED / FAILED / PROCESSING_ERROR; SUCCEEDED -> refund ->
REFUNDED. Confirm and refund are idempotent: repeating them returns
the recorded outcome and seals nothing new.
"""

import hashlib
import hmac
import json
import time
import uuid

OWNER = "SLMK Jesse Martinez Junior"
SANDBOX_GENESIS = "SANDBOX_GENESIS_CRSMCPAI_ALPHA"
SANDBOX_SIGNING_SECRET = "sbx_test_signing_secret_public_fixture"
MAX_AMOUNT_CENTS = 1_000_000
CURRENCIES = ("usd",)

# Publicly documented industry test fixtures. The card numbers are the
# test numbers payment providers publish for exactly this purpose;
# they are not real cards and cannot move money anywhere.
TEST_TOKENS = {
    "tok_test_visa_success": {
        "card_last4": "4242", "brand": "visa", "outcome": "approve",
        "note": "Standard success test card (4242...)."},
    "tok_test_visa_debit_success": {
        "card_last4": "5556", "brand": "visa-debit", "outcome": "approve",
        "note": "Debit success test card."},
    "tok_test_generic_decline": {
        "card_last4": "0002", "brand": "visa", "outcome": "decline",
        "failure_code": "card_declined",
        "note": "Generic decline test card."},
    "tok_test_insufficient_funds": {
        "card_last4": "9995", "brand": "visa", "outcome": "decline",
        "failure_code": "insufficient_funds",
        "note": "Insufficient funds test card."},
    "tok_test_expired_card": {
        "card_last4": "0069", "brand": "visa", "outcome": "decline",
        "failure_code": "expired_card",
        "note": "Expired card test card."},
    "tok_test_incorrect_cvc": {
        "card_last4": "0127", "brand": "visa", "outcome": "decline",
        "failure_code": "incorrect_cvc",
        "note": "Incorrect CVC test card."},
    "tok_test_processing_error": {
        "card_last4": "0119", "brand": "visa", "outcome": "error",
        "failure_code": "processing_error",
        "note": "Processing error test card (retryable)."},
}

_INTENTS = {}          # intent_id -> record
_IDEMPOTENCY = {}      # idempotency_key -> intent_id
_MOCK_CHAIN = []       # sandbox hash chain (mock ledger records)
_WEBHOOKS = {}         # event_id -> simulated event


def _seal(event_type, payload):
    """Append one mock record to the sandbox chain, production style:
    index, ts, owner, payload, prev_hash, SHA3-512 block hash."""
    prev = _MOCK_CHAIN[-1]["block_hash"] if _MOCK_CHAIN else \
        hashlib.sha3_512(SANDBOX_GENESIS.encode()).hexdigest()
    block = {
        "index": len(_MOCK_CHAIN),
        "ts": time.time(),
        "owner": OWNER,
        "payload": {"sandbox": True, "event": event_type, **payload},
        "prev_hash": prev,
    }
    block["block_hash"] = hashlib.sha3_512(
        json.dumps(block, sort_keys=True).encode()).hexdigest()
    block["hash"] = block["block_hash"]
    _MOCK_CHAIN.append(block)
    return block


def verify_mock_chain():
    """Recompute every mock block hash and link, production style."""
    if not _MOCK_CHAIN:
        return True
    genesis = hashlib.sha3_512(SANDBOX_GENESIS.encode()).hexdigest()
    if _MOCK_CHAIN[0]["prev_hash"] != genesis:
        return False
    for i, block in enumerate(_MOCK_CHAIN):
        check = {k: v for k, v in block.items()
                 if k not in ("block_hash", "hash")}
        expected = hashlib.sha3_512(
            json.dumps(check, sort_keys=True).encode()).hexdigest()
        if block.get("block_hash") != expected:
            return False
        if i > 0 and block.get("prev_hash") != \
                _MOCK_CHAIN[i - 1].get("block_hash"):
            return False
    return True


def _public_intent(rec):
    return {k: rec[k] for k in (
        "intent_id", "amount_cents", "currency", "description",
        "state", "failure_code", "token", "card_last4", "created_ts",
        "updated_ts")}


def create_intent(amount_cents, currency="usd", idempotency_key="",
                  description=""):
    """Validation gates run first, in the stack's fulfillment order:
    an invalid request is rejected before anything is recorded."""
    if isinstance(amount_cents, bool) or not isinstance(amount_cents, int):
        return {"ok": False, "error": "amount_cents must be an integer"}
    if amount_cents <= 0:
        return {"ok": False, "error": "amount_cents must be positive"}
    if amount_cents > MAX_AMOUNT_CENTS:
        return {"ok": False,
                "error": f"amount exceeds sandbox max {MAX_AMOUNT_CENTS}"}
    currency = (currency or "usd").lower()
    if currency not in CURRENCIES:
        return {"ok": False,
                "error": f"currency '{currency}' not enabled in sandbox"}
    if idempotency_key and idempotency_key in _IDEMPOTENCY:
        rec = _INTENTS[_IDEMPOTENCY[idempotency_key]]
        return {"ok": True, "idempotent_replay": True,
                "intent": _public_intent(rec)}
    intent_id = "pi_test_" + uuid.uuid4().hex[:24]
    now = time.time()
    rec = {
        "intent_id": intent_id, "amount_cents": amount_cents,
        "currency": currency, "description": description or "",
        "state": "REQUIRES_CONFIRMATION", "failure_code": None,
        "token": None, "card_last4": None,
        "created_ts": now, "updated_ts": now,
    }
    _INTENTS[intent_id] = rec
    if idempotency_key:
        _IDEMPOTENCY[idempotency_key] = intent_id
    _seal("intent_created", {"intent_id": intent_id,
                             "amount_cents": amount_cents,
                             "currency": currency})
    return {"ok": True, "intent": _public_intent(rec)}


def confirm_intent(intent_id, token):
    rec = _INTENTS.get(intent_id)
    if not rec:
        return {"ok": False, "error": "unknown intent"}
    if rec["state"] in ("SUCCEEDED", "FAILED", "REFUNDED"):
        return {"ok": True, "idempotent_replay": True,
                "intent": _public_intent(rec)}
    profile = TEST_TOKENS.get(token or "")
    if profile is None:
        return {"ok": False,
                "error": "unknown test token — sandbox accepts only "
                         "the documented test tokens"}
    rec["token"] = token
    rec["card_last4"] = profile["card_last4"]
    rec["updated_ts"] = time.time()
    if profile["outcome"] == "approve":
        rec["state"] = "SUCCEEDED"
        _seal("payment_succeeded", {"intent_id": intent_id,
                                    "amount_cents": rec["amount_cents"],
                                    "card_last4": profile["card_last4"]})
    elif profile["outcome"] == "decline":
        rec["state"] = "FAILED"
        rec["failure_code"] = profile["failure_code"]
        _seal("payment_failed", {"intent_id": intent_id,
                                 "failure_code": profile["failure_code"],
                                 "card_last4": profile["card_last4"]})
    else:
        # Processing error: no terminal state, nothing sealed as a
        # payment outcome; the intent may be confirmed again.
        rec["state"] = "REQUIRES_CONFIRMATION"
        rec["failure_code"] = profile["failure_code"]
        _seal("payment_processing_error",
              {"intent_id": intent_id,
               "failure_code": profile["failure_code"]})
        return {"ok": False, "retryable": True,
                "error": "processing_error — simulated provider error, "
                         "no charge recorded",
                "intent": _public_intent(rec)}
    return {"ok": True, "intent": _public_intent(rec)}


def refund_intent(intent_id):
    rec = _INTENTS.get(intent_id)
    if not rec:
        return {"ok": False, "error": "unknown intent"}
    if rec["state"] == "REFUNDED":
        return {"ok": True, "idempotent_replay": True,
                "intent": _public_intent(rec)}
    if rec["state"] != "SUCCEEDED":
        return {"ok": False,
                "error": f"cannot refund an intent in state "
                         f"{rec['state']}"}
    rec["state"] = "REFUNDED"
    rec["updated_ts"] = time.time()
    _seal("refund_issued", {"intent_id": intent_id,
                            "amount_cents": rec["amount_cents"]})
    return {"ok": True, "intent": _public_intent(rec)}


def get_intent(intent_id):
    rec = _INTENTS.get(intent_id)
    if not rec:
        return {"ok": False, "error": "unknown intent"}
    return {"ok": True, "intent": _public_intent(rec)}


def _sign(payload_bytes):
    return hmac.new(SANDBOX_SIGNING_SECRET.encode(), payload_bytes,
                    hashlib.sha256).hexdigest()


def simulate_webhook(intent_id, event_type=""):
    """Build a provider-shaped simulated webhook event for an intent
    and sign it, so the receiving/verification path can be exercised
    end to end without any live provider."""
    rec = _INTENTS.get(intent_id)
    if not rec:
        return {"ok": False, "error": "unknown intent"}
    if not event_type:
        event_type = {"SUCCEEDED": "payment.succeeded",
                      "FAILED": "payment.failed",
                      "REFUNDED": "charge.refunded"}.get(
                          rec["state"], "payment.updated")
    event = {
        "id": "evt_test_" + uuid.uuid4().hex[:24],
        "type": event_type,
        "sandbox": True,
        "created": int(time.time()),
        "data": {"object": _public_intent(rec)},
    }
    body = json.dumps(event, sort_keys=True).encode()
    event["signature"] = _sign(body)
    _WEBHOOKS[event["id"]] = event
    _seal("webhook_simulated", {"event_id": event["id"],
                                "type": event_type,
                                "intent_id": intent_id})
    return {"ok": True, "event": event}


def verify_webhook(payload, signature):
    """Verify a simulated webhook: the signature must match the exact
    payload as simulated. Any tampering fails."""
    if not isinstance(payload, dict) or not signature:
        return {"ok": False, "error": "payload and signature required"}
    body = json.dumps(payload, sort_keys=True).encode()
    expected = _sign(body)
    if not hmac.compare_digest(expected, str(signature)):
        _seal("webhook_verification_failed",
              {"event_id": payload.get("id", "")})
        return {"ok": False, "verified": False,
                "error": "signature mismatch"}
    _seal("webhook_verified", {"event_id": payload.get("id", ""),
                               "type": payload.get("type", "")})
    return {"ok": True, "verified": True,
            "event_id": payload.get("id", "")}


def list_tokens():
    return {"tokens": {k: {"card_last4": v["card_last4"],
                           "brand": v["brand"],
                           "outcome": v["outcome"],
                           "note": v["note"]}
                       for k, v in TEST_TOKENS.items()}}


def mock_ledger(limit=50):
    return {"sandbox": True, "chain_valid": verify_mock_chain(),
            "length": len(_MOCK_CHAIN),
            "records": _MOCK_CHAIN[-limit:] if limit else _MOCK_CHAIN}


def sandbox_status():
    by_state = {}
    for rec in _INTENTS.values():
        by_state[rec["state"]] = by_state.get(rec["state"], 0) + 1
    return {
        "module": "sandbox_payments", "owner": OWNER, "sandbox": True,
        "real_money": False, "provider_calls": 0,
        "production_ledger_touched": False,
        "state_storage": "in-memory — resets on restart, by design",
        "max_amount_cents": MAX_AMOUNT_CENTS,
        "currencies": list(CURRENCIES),
        "intents_total": len(_INTENTS), "intents_by_state": by_state,
        "mock_ledger_length": len(_MOCK_CHAIN),
        "mock_chain_valid": verify_mock_chain(),
        "webhooks_simulated": len(_WEBHOOKS),
        "test_tokens": len(TEST_TOKENS),
    }
