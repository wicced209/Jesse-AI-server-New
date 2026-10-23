"""
x402 payment plumbing for the SOLVA Agent API (paid agent endpoints).

Implements the x402 protocol wire flow (v1) directly against the
facilitator's documented HTTP interface:

  1. Client calls a paid endpoint with no payment header
     -> server replies HTTP 402 with a JSON body:
        {"x402Version": 1, "error": ..., "accepts": [PaymentRequirements]}
  2. Client retries with header  X-PAYMENT: base64(payment payload JSON)
     where the payload carries an EIP-3009 TransferWithAuthorization
     signed by the payer's own wallet.
  3. Server asks the facilitator to VERIFY the payment
     (POST {facilitator}/verify) -- verification moves NO money.
  4. Only after the endpoint's own payload validation AND facilitator
     verification pass does the server do the work, and only then does
     it ask the facilitator to SETTLE (POST {facilitator}/settle).
     Settlement is what actually moves the USDC.
  5. Server returns the result plus an X-PAYMENT-RESPONSE header
     (base64 JSON of the settle response).

Fulfillment standard (owner's rule): a request that fails payload
validation is rejected BEFORE any payment step -- the facilitator is
never even called -- and settlement only ever happens after the paid
work has succeeded. A failed call is never charged.

Key safety: in the x402 "exact" scheme the server needs NO private key
and NO secret of any kind. It only needs the PUBLIC receiving address
(payTo). The payer signs; the facilitator settles. Nothing in this
module reads, stores, or logs any key material.

Why not the official x402 Python SDK (v2.x)? Evaluated 2026-10-22:
the SDK's FastAPI support is an app-wide ASGI middleware that checks
payment BEFORE the route handler runs and settles from the middleware
response pipeline. That fixed ordering cannot enforce this stack's
validation-before-payment ordering per endpoint, wraps a ~100-route
server (plus WebSockets) to guard two routes, and adds a large,
fast-moving dependency to requirements.txt. The v1 wire format used
here is the stable documented interface that the Coinbase CDP
facilitator itself exposes (/verify, /settle, /supported), so the
manual implementation interoperates with standard x402 clients.
Revisit the SDK if more paid endpoints are added.

Configuration (environment variables, all with safe defaults):
  X402_PAYTO_ADDRESS       public receiving address (NOT a secret)
  X402_NETWORK             x402 network name           (default "base")
  X402_FACILITATOR_URL     facilitator base URL        (default CDP)
  X402_FACILITATOR_API_KEY optional bearer token for the facilitator
                           (e.g. CDP credentials at deploy time; never
                           a wallet key; empty = no auth header)
  X402_ASSET_ADDRESS       token contract (default USDC on Base)
  X402_ASSET_DECIMALS      token decimals              (default 6)
  X402_ASSET_NAME          EIP-712 token name          (default "USD Coin")
  X402_ASSET_VERSION       EIP-712 token version       (default "2")
  X402_PRICE_SEAL_USD      seal price in USD           (default "0.02")
  X402_PRICE_VERIFY_USD    verify price in USD         (default "0.005")
  X402_MAX_TIMEOUT_SECONDS payment validity window     (default 300)
  X402_MAX_DATA_CHARS      max serialized seal data    (default 8192)
  X402_PUBLIC_BASE_URL     optional public base URL used in the
                           "resource" field (proxy-safe); empty = use
                           the request URL as seen by the server
  X402_ENABLED             "true"/"false" kill switch  (default "true")

Owner: SLMK Jesse Martinez Junior.
"""

import base64
import json
import os
import time
from decimal import Decimal, InvalidOperation

import requests

X402_VERSION = 1
SCHEME = "exact"

DEFAULT_PAYTO_ADDRESS = "0x42cF14893dE5aE59799043bE8032428FdFFB4452"
DEFAULT_FACILITATOR_URL = "https://api.cdp.coinbase.com/platform/v2/x402"
# USDC on Base mainnet (Circle native USDC contract).
DEFAULT_ASSET_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

_FACILITATOR_TIMEOUT_SECONDS = 20


def _env(name, default):
    value = os.environ.get(name, "")
    return value if value != "" else default


def x402_enabled() -> bool:
    return _env("X402_ENABLED", "true").strip().lower() in ("1", "true", "yes", "on")


def payto_address() -> str:
    return _env("X402_PAYTO_ADDRESS", DEFAULT_PAYTO_ADDRESS)


def network() -> str:
    return _env("X402_NETWORK", "base")


def facilitator_url() -> str:
    return _env("X402_FACILITATOR_URL", DEFAULT_FACILITATOR_URL).rstrip("/")


def asset_address() -> str:
    return _env("X402_ASSET_ADDRESS", DEFAULT_ASSET_ADDRESS)


def asset_decimals() -> int:
    try:
        return int(_env("X402_ASSET_DECIMALS", "6"))
    except ValueError:
        return 6


def max_timeout_seconds() -> int:
    try:
        return int(_env("X402_MAX_TIMEOUT_SECONDS", "300"))
    except ValueError:
        return 300


def max_data_chars() -> int:
    try:
        return int(_env("X402_MAX_DATA_CHARS", "8192"))
    except ValueError:
        return 8192


def price_usd(kind: str) -> str:
    """Configured USD price string for 'seal' or 'verify'."""
    if kind == "seal":
        return _env("X402_PRICE_SEAL_USD", "0.02")
    return _env("X402_PRICE_VERIFY_USD", "0.005")


def price_atomic(kind: str) -> str:
    """USD price converted to token atomic units, as a decimal string."""
    try:
        usd = Decimal(price_usd(kind))
    except InvalidOperation:
        usd = Decimal("0")
    atomic = int(usd * (Decimal(10) ** asset_decimals()))
    return str(atomic)


def build_requirements(resource_url: str, kind: str, description: str) -> dict:
    """x402 PaymentRequirements object for one paid endpoint."""
    return {
        "scheme": SCHEME,
        "network": network(),
        "maxAmountRequired": price_atomic(kind),
        "resource": resource_url,
        "description": description,
        "mimeType": "application/json",
        "payTo": payto_address(),
        "maxTimeoutSeconds": max_timeout_seconds(),
        "asset": asset_address(),
        "extra": {
            "name": _env("X402_ASSET_NAME", "USD Coin"),
            "version": _env("X402_ASSET_VERSION", "2"),
        },
    }


def challenge_body(requirements: dict, error: str) -> dict:
    """The JSON body of an HTTP 402 response."""
    return {"x402Version": X402_VERSION, "error": error, "accepts": [requirements]}


class PaymentStructuralError(Exception):
    """The X-PAYMENT header is malformed or does not match the requirements."""


def _is_address(value) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 42
        and value.startswith("0x")
        and all(c in "0123456789abcdefABCDEF" for c in value[2:])
    )


def decode_payment_header(header_value: str) -> dict:
    """Base64-decode and JSON-parse the X-PAYMENT header. Raises on bad input."""
    try:
        raw = base64.b64decode(header_value, validate=True)
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        raise PaymentStructuralError("payment header is not valid base64 JSON")
    if not isinstance(payload, dict):
        raise PaymentStructuralError("payment payload is not a JSON object")
    return payload


def check_payment_structure(payload: dict, requirements: dict) -> dict:
    """
    Cheap local checks on a decoded payment payload BEFORE the facilitator
    is involved: version, scheme, network, destination, amount, validity
    window, and presence of signature material. Cryptographic verification
    (EIP-3009 signature recovery) is the facilitator's job, not ours.
    Returns the authorization dict on success; raises PaymentStructuralError.
    """
    if payload.get("x402Version") != X402_VERSION:
        raise PaymentStructuralError("unsupported x402Version")
    if payload.get("scheme") != SCHEME:
        raise PaymentStructuralError("unsupported payment scheme")
    if payload.get("network") != requirements["network"]:
        raise PaymentStructuralError("payment network does not match this endpoint")
    inner = payload.get("payload")
    if not isinstance(inner, dict):
        raise PaymentStructuralError("payment payload missing 'payload' object")
    auth = inner.get("authorization")
    if not isinstance(auth, dict):
        raise PaymentStructuralError("payment payload missing EIP-3009 authorization")
    signature = inner.get("signature")
    if not (isinstance(signature, str) and signature.startswith("0x") and len(signature) >= 130):
        raise PaymentStructuralError("payment payload missing a signature")
    if not _is_address(auth.get("from")):
        raise PaymentStructuralError("authorization 'from' is not an address")
    to = auth.get("to")
    if not _is_address(to) or to.lower() != requirements["payTo"].lower():
        raise PaymentStructuralError("authorization 'to' is not the required payTo address")
    try:
        value = int(auth.get("value", "0"))
        required = int(requirements["maxAmountRequired"])
    except (TypeError, ValueError):
        raise PaymentStructuralError("authorization 'value' is not an integer amount")
    if value < required:
        raise PaymentStructuralError("payment amount is below the required price")
    now = int(time.time())
    try:
        valid_after = int(auth.get("validAfter", "0"))
        valid_before = int(auth.get("validBefore", "0"))
    except (TypeError, ValueError):
        raise PaymentStructuralError("authorization validity window is not numeric")
    if valid_before <= now:
        raise PaymentStructuralError("payment authorization has expired")
    if valid_after > now + 600:
        raise PaymentStructuralError("payment authorization is not yet valid")
    if not auth.get("nonce"):
        raise PaymentStructuralError("authorization missing nonce")
    return auth


class FacilitatorError(Exception):
    """The facilitator could not be reached or answered with an error."""


def _facilitator_post(path: str, payload: dict, requirements: dict) -> dict:
    url = facilitator_url() + path
    body = {
        "x402Version": X402_VERSION,
        "paymentPayload": payload,
        "paymentRequirements": requirements,
    }
    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get("X402_FACILITATOR_API_KEY", "")
    if api_key:
        # Auth credential for the facilitator service only (e.g. CDP).
        # This is never a wallet key; the server holds no wallet keys.
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        resp = requests.post(url, json=body, headers=headers,
                             timeout=_FACILITATOR_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        raise FacilitatorError(f"facilitator unreachable: {exc.__class__.__name__}")
    if resp.status_code != 200:
        raise FacilitatorError(f"facilitator returned HTTP {resp.status_code}")
    try:
        data = resp.json()
    except Exception:
        raise FacilitatorError("facilitator returned a non-JSON response")
    if not isinstance(data, dict):
        raise FacilitatorError("facilitator returned an unexpected response")
    return data


def verify_payment(payload: dict, requirements: dict) -> dict:
    """Ask the facilitator to verify (NOT settle) a payment. Returns its verdict."""
    return _facilitator_post("/verify", payload, requirements)


def settle_payment(payload: dict, requirements: dict) -> dict:
    """Ask the facilitator to settle a previously verified payment on-chain."""
    return _facilitator_post("/settle", payload, requirements)


def encode_payment_response(settle_result: dict) -> str:
    """Base64 JSON for the X-PAYMENT-RESPONSE response header."""
    return base64.b64encode(json.dumps(settle_result).encode("utf-8")).decode("ascii")


def module_status() -> dict:
    return {
        "module": "x402_payments",
        "enabled": x402_enabled(),
        "x402_version": X402_VERSION,
        "scheme": SCHEME,
        "network": network(),
        "pay_to": payto_address(),
        "asset": asset_address(),
        "facilitator": facilitator_url(),
        "prices": {
            "seal": {"usd": price_usd("seal"), "atomic": price_atomic("seal")},
            "verify": {"usd": price_usd("verify"), "atomic": price_atomic("verify")},
        },
    }
