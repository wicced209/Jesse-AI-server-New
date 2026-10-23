"""
SOLVA Agent API — paid Golden Ledger endpoints (x402).

Two machine-to-machine products for AI agents, paid per call in USDC
over the x402 protocol (see api/x402_payments.py for the wire flow):

  POST /agent/ledger/seal
      Body: {"data": <any JSON value or string>, "reference": <optional str>}
      Seals the data into the production Golden Ledger hash chain
      (memory/ledger.py, the same path the live stack seals through)
      and returns {"index", "block_hash", "prev_hash", ...} so the
      caller holds a publicly verifiable receipt.

  POST /agent/ledger/verify
      Body: {"index": <int>} and/or {"block_hash": "<128 hex chars>"}
      Re-checks the block against the chain: recomputes its SHA3-512
      hash from its stored fields and confirms its previous-hash link.
      Returns {"found", "valid", "hash_matches", "linkage_ok", ...}.

  GET  /agent/ledger/status   (free)
      Prices, network, receiving address, chain state.

Fulfillment standard (owner's rule), enforced by the handler order in
_handle_paid_call below:
  1. The request body is parsed and validated FIRST. An invalid body
     is rejected (400/422) before the payment header is even read and
     before the facilitator is contacted -- nothing can be charged.
  2. A structurally wrong payment (wrong network, wrong destination,
     too small, expired) is rejected with a fresh 402 challenge --
     again with no facilitator call and no settlement.
  3. The facilitator VERIFIES the payment (verification moves no
     money). An invalid payment gets a 402, never a settlement.
  4. The paid work runs. If the work itself fails, the call fails
     WITHOUT settlement.
  5. Only then does the facilitator SETTLE. The result is returned
     together with the settlement receipt (X-PAYMENT-RESPONSE header).
     If settlement fails, the result is withheld and the call returns
     502 -- the caller is not charged for a result it did not get.

The server holds no wallet keys (x402 "exact" scheme: the payer signs,
the facilitator settles); configuration carries the PUBLIC receiving
address only. Owner: SLMK Jesse Martinez Junior.
"""

import hashlib
import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from api import x402_payments as x402

router = APIRouter(prefix="/agent/ledger", tags=["agent-ledger-x402"])

SEAL_DESCRIPTION = (
    "SOLVA Agent API - Golden Ledger seal: the submitted data is sealed "
    "into the CRSMCPAI Alpha Golden Ledger SHA3-512 hash chain and the "
    "response returns the block index and block hash as a verifiable receipt."
)
VERIFY_DESCRIPTION = (
    "SOLVA Agent API - Golden Ledger verification: a block (by index "
    "and/or block hash) is re-checked against the Golden Ledger chain - "
    "its hash is recomputed from its stored fields and its chain link "
    "is confirmed."
)


class _WorkFailed(Exception):
    """The paid work itself failed; the call must end WITHOUT settlement."""

    def __init__(self, status_code: int, body: dict):
        super().__init__(body.get("error", "work_failed"))
        self.status_code = status_code
        self.body = body


def _resource_url(request: Request) -> str:
    base = x402._env("X402_PUBLIC_BASE_URL", "")
    if base:
        return base.rstrip("/") + request.url.path
    return str(request.url)


# ── payload validation (runs before ANY payment handling) ────────────

def _validate_seal(body) -> str | None:
    if not isinstance(body, dict):
        return "body must be a JSON object"
    if "data" not in body or body["data"] is None:
        return "missing required field: data"
    data = body["data"]
    if isinstance(data, str) and not data.strip():
        return "data must not be empty"
    if isinstance(data, (dict, list)) and len(data) == 0:
        return "data must not be empty"
    try:
        serialized = json.dumps(data)
    except (TypeError, ValueError):
        return "data is not JSON-serializable"
    if len(serialized) > x402.max_data_chars():
        return f"data exceeds the {x402.max_data_chars()} character limit"
    reference = body.get("reference")
    if reference is not None and (not isinstance(reference, str) or len(reference) > 128):
        return "reference must be a string of at most 128 characters"
    return None


def _validate_verify(body) -> str | None:
    if not isinstance(body, dict):
        return "body must be a JSON object"
    index = body.get("index")
    block_hash = body.get("block_hash")
    if index is None and block_hash is None:
        return "provide at least one of: index, block_hash"
    if index is not None:
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            return "index must be a non-negative integer"
    if block_hash is not None:
        if (
            not isinstance(block_hash, str)
            or len(block_hash) != 128
            or any(c not in "0123456789abcdefABCDEF" for c in block_hash)
        ):
            return "block_hash must be a 128-character hex SHA3-512 hash"
    return None


# ── the paid work (runs only after verification, before settlement) ──

def _do_seal(body: dict, payer: str) -> dict:
    from memory.ledger import create_event, verify_chain

    payload = {
        "type": "AGENT_LEDGER_SEAL",
        "source": "x402_agent_api",
        "payer": payer,
        "data": body["data"],
    }
    if body.get("reference"):
        payload["reference"] = body["reference"]
    block = create_event(payload)
    return {
        "sealed": True,
        "index": block["index"],
        "block_hash": block["block_hash"],
        "prev_hash": block["prev_hash"],
        "timestamp": block["ts"],
        "chain_valid": verify_chain(),
    }


def _block_hash_matches(block: dict) -> bool:
    """Recompute a Golden Ledger block hash the way memory/ledger.py does."""
    check = {k: v for k, v in block.items() if k not in ("block_hash", "hash")}
    expected = hashlib.sha3_512(json.dumps(check, sort_keys=True).encode()).hexdigest()
    return block.get("block_hash") == expected


def _do_verify(body: dict, payer: str) -> dict:
    from memory.ledger import GENESIS, get_ledger, verify_chain

    chain = get_ledger()
    block = None
    if body.get("index") is not None:
        idx = body["index"]
        if 0 <= idx < len(chain):
            block = chain[idx]
    else:
        wanted = body["block_hash"].lower()
        for candidate in chain:
            if str(candidate.get("block_hash", "")).lower() == wanted:
                block = candidate
                break
    if block is None:
        # A definitive answer over the real chain: the block is not there.
        return {
            "found": False,
            "valid": False,
            "chain_total_blocks": len(chain),
            "chain_valid": verify_chain(),
        }
    index = block["index"]
    hash_matches = _block_hash_matches(block)
    expected_prev = GENESIS if index == 0 else chain[index - 1].get("block_hash")
    linkage_ok = block.get("prev_hash") == expected_prev
    hash_supplied_matches = True
    if body.get("block_hash") is not None:
        hash_supplied_matches = (
            str(block.get("block_hash", "")).lower() == body["block_hash"].lower()
        )
    valid = bool(hash_matches and linkage_ok and hash_supplied_matches)
    return {
        "found": True,
        "valid": valid,
        "index": index,
        "block_hash": block.get("block_hash"),
        "hash_matches": hash_matches,
        "linkage_ok": linkage_ok,
        "supplied_hash_matches": hash_supplied_matches,
        "chain_total_blocks": len(chain),
        "chain_valid": verify_chain(),
        "block": block,
    }


# ── shared paid-call pipeline ─────────────────────────────────────────

async def _handle_paid_call(request: Request, kind: str, description: str,
                            validate_fn, work_fn) -> JSONResponse:
    if not x402.x402_enabled():
        return JSONResponse(status_code=503, content={
            "error": "agent_endpoints_disabled",
            "detail": "The x402 agent endpoints are currently disabled.",
        })

    # Step 1: parse + validate the payload FIRST (before payment exists
    # in the picture at all). A bad payload can never be charged.
    raw = await request.body()
    if not raw:
        return JSONResponse(status_code=400, content={
            "error": "invalid_json", "detail": "request body is empty"})
    try:
        body = json.loads(raw.decode("utf-8"))
    except Exception:
        return JSONResponse(status_code=400, content={
            "error": "invalid_json", "detail": "request body is not valid JSON"})
    problem = validate_fn(body)
    if problem is not None:
        return JSONResponse(status_code=422, content={
            "error": "validation_failed", "detail": problem})

    requirements = x402.build_requirements(_resource_url(request), kind, description)

    # Step 2: no payment header -> issue the 402 challenge.
    header = request.headers.get("x-payment")
    if not header:
        return JSONResponse(status_code=402, content=x402.challenge_body(
            requirements, "payment required"))

    # Step 3: structural checks on the payment, still no facilitator.
    try:
        payment_payload = x402.decode_payment_header(header)
        x402.check_payment_structure(payment_payload, requirements)
    except x402.PaymentStructuralError as exc:
        return JSONResponse(status_code=402, content=x402.challenge_body(
            requirements, f"invalid payment: {exc}"))

    # Step 4: facilitator verification (moves no money).
    try:
        verdict = x402.verify_payment(payment_payload, requirements)
    except x402.FacilitatorError as exc:
        return JSONResponse(status_code=502, content={
            "error": "payment_verification_unavailable", "detail": str(exc)})
    if not verdict.get("isValid"):
        reason = verdict.get("invalidReason") or "payment_invalid"
        return JSONResponse(status_code=402, content=x402.challenge_body(
            requirements, f"payment rejected: {reason}"))
    payer = verdict.get("payer") or ""

    # Step 5: do the paid work. Failure here = no settlement, no charge.
    try:
        result = work_fn(body, payer)
    except _WorkFailed as exc:
        return JSONResponse(status_code=exc.status_code, content=exc.body)
    except Exception:
        return JSONResponse(status_code=500, content={
            "error": "work_failed",
            "detail": "the paid operation failed; payment was not settled"})

    # Step 6: settle, then deliver the result with the receipt.
    try:
        settle = x402.settle_payment(payment_payload, requirements)
    except x402.FacilitatorError as exc:
        return JSONResponse(status_code=502, content={
            "error": "settlement_failed", "detail": str(exc),
            "note": "the work completed but the result is withheld because "
                    "settlement did not complete"})
    if not settle.get("success"):
        return JSONResponse(status_code=502, content={
            "error": "settlement_failed",
            "detail": settle.get("errorReason") or "facilitator did not settle",
            "note": "the work completed but the result is withheld because "
                    "settlement did not complete"})

    result["payment"] = {
        "scheme": x402.SCHEME,
        "network": settle.get("network") or requirements["network"],
        "payer": settle.get("payer") or payer,
        "pay_to": requirements["payTo"],
        "asset": requirements["asset"],
        "amount_atomic": requirements["maxAmountRequired"],
        "amount_usd": x402.price_usd(kind),
        "transaction": settle.get("transaction"),
    }
    response = JSONResponse(content=result)
    response.headers["X-PAYMENT-RESPONSE"] = x402.encode_payment_response(settle)
    return response


@router.post("/seal", summary="Seal data into the Golden Ledger (x402 paid)")
async def agent_ledger_seal(request: Request):
    return await _handle_paid_call(
        request, "seal", SEAL_DESCRIPTION, _validate_seal, _do_seal)


@router.post("/verify", summary="Verify a Golden Ledger block (x402 paid)")
async def agent_ledger_verify(request: Request):
    return await _handle_paid_call(
        request, "verify", VERIFY_DESCRIPTION, _validate_verify, _do_verify)


@router.get("/status", summary="x402 agent endpoint status (free)")
async def agent_ledger_status():
    from memory.ledger import get_ledger, verify_chain

    status = x402.module_status()
    chain = get_ledger()
    status.update({
        "service": "SOLVA Agent API - Golden Ledger",
        "endpoints": {
            "seal": "POST /agent/ledger/seal",
            "verify": "POST /agent/ledger/verify",
        },
        "chain_total_blocks": len(chain),
        "chain_valid": verify_chain(),
    })
    return status


def module_status() -> dict:
    return {"module": "agent_ledger", "status": "ACTIVE",
            "routes": ["/agent/ledger/seal", "/agent/ledger/verify",
                       "/agent/ledger/status"]}
