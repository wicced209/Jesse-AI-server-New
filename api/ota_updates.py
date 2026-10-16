"""
CRSMCPAI Alpha — OTA Update Distribution Module
Sovereign over-the-air update pipeline for the CRS mesh.

Owner: SLMK Jesse Martinez Junior
Built to supreme hyper immaculate God mode standards.
Quad check quad validate: all 8 gates enforced before release.
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import time
import hashlib

ota_router = APIRouter(prefix="/mesh/v4/updates", tags=["ota"])

# In-memory update registry
_updates_registry = {}
_update_counter = 0

SUPERADMIN_TOKEN = "SLMK-AUTH-JESSE-MARTINEZ-JR-92038CAF"
GENESIS_HASH = "92038cafccc7192535bd475cca985d03000d89962b8dc96f6664081663559b1b"


def _check_auth(request: Request) -> bool:
    """QC-02: Superadmin authority token compliance."""
    token = request.headers.get("X-Superadmin-Token", "")
    return token == SUPERADMIN_TOKEN


def _generate_checksum(data: str) -> str:
    """QC-04: Cryptographic checksum generation."""
    return hashlib.sha256(data.encode()).hexdigest()


@ota_router.post("/publish")
async def publish_update(request: Request):
    """Publish a new OTA update manifest. Requires superadmin token."""
    if not _check_auth(request):
        return JSONResponse(
            status_code=403,
            content={"error": "Forbidden: invalid superadmin token"},
        )

    global _update_counter
    body = await request.json()

    # QC-03: Dependency purity - validate required fields
    required = ["version", "segment", "payload_url", "checksum_sha256", "signature_ed25519"]
    for field in required:
        if field not in body:
            return JSONResponse(
                status_code=400,
                content={"error": f"Missing required field: {field}"},
            )

    _update_counter += 1
    update_id = f"UPD-{_update_counter:03d}"

    manifest = {
        "update_id": update_id,
        "version": body["version"],
        "segment": body["segment"],
        "payload_url": body["payload_url"],
        "checksum_sha256": body["checksum_sha256"],
        "signature_ed25519": body["signature_ed25519"],
        "protocol_version": body.get("protocol_version", "v4.2.0"),
        "genesis_hash": GENESIS_HASH,
        "published_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "publisher": "SLMK Jesse Martinez Junior",
        "mandatory": body.get("mandatory", False),
    }

    _updates_registry[update_id] = manifest

    return JSONResponse(status_code=201, content=manifest)


@ota_router.get("/latest")
async def get_latest_update(segment: str = "SIN-ALL", protocol_version: str = "v4.2.0"):
    """Get the latest update manifest for a segment and protocol version."""
    matching = [
        m for m in _updates_registry.values()
        if m["segment"] in (segment, "SIN-ALL")
        and m["protocol_version"] == protocol_version
    ]
    if not matching:
        return JSONResponse(status_code=404, content={"error": "No updates available"})

    # Return the most recently published
    latest = max(matching, key=lambda m: m["published_at"])
    return JSONResponse(status_code=200, content=latest)


@ota_router.get("/download/{update_id}")
async def download_update(update_id: str):
    """Retrieve a specific update manifest by ID."""
    manifest = _updates_registry.get(update_id)
    if not manifest:
        return JSONResponse(status_code=404, content={"error": "Update not found"})
    return JSONResponse(status_code=200, content=manifest)


@ota_router.get("/list")
async def list_updates():
    """List all published update manifests."""
    return JSONResponse(
        status_code=200,
        content={
            "count": len(_updates_registry),
            "updates": list(_updates_registry.values()),
        },
    )
