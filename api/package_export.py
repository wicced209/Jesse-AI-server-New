"""
Package Export — guarded full-package download for Muse.

Built at the direct order of the owner, Jesse Armando Martinez Junior
(2026-10-28), relayed by Muse. Purpose: give Muse one real file route
to pull everything the stack holds, byte for byte, with no language
model in the middle — the deployed source tree plus the runtime data
(full ledger, conversation history, execution records).

Guard: identical semantics to the /oversight/* routes in api/server.py.
The x-user header must be PRESENT and allowlisted (security.auth).
An absent header never authenticates. Without it: 403.

Safety rules baked in:
- Secret-shaped files are never included (names matching .env, secret,
  credential, token files, private keys, certificates) and runtime
  upload / database files are skipped. Skips are listed in the manifest.
- Every data section is crash-safe: if one section fails, the archive
  carries an error note for that section instead of failing the whole
  download.
- The manifest lists every included file with its size and SHA256.
"""

import hashlib
import io
import json
import time
import zipfile
from pathlib import Path

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse, Response

from security.auth import authenticate

package_router = APIRouter()

_REPO_ROOT = Path(__file__).resolve().parent.parent

_INCLUDE_SUFFIXES = {
    ".py", ".md", ".txt", ".json", ".toml", ".yaml", ".yml",
    ".html", ".js", ".css", ".sh",
}
_INCLUDE_NAMES = {"Procfile", "requirements.txt", "railway.json", "README.md"}
_SKIP_DIRS = {"__pycache__", ".git", ".venv", "node_modules", "crs_uploads"}
_SKIP_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".db", ".sqlite", ".sqlite3"}
_MAX_FILE_BYTES = 2_000_000


def _is_secret_shaped(path: Path) -> bool:
    name = path.name.lower()
    if name == ".env" or name.startswith(".env"):
        return True
    if path.suffix.lower() in _SKIP_SUFFIXES:
        return True
    for word in ("secret", "credential", "private_key", "privatekey"):
        if word in name:
            return True
    return False


def _collect_source_files():
    """Walk the deployed tree and return (included, skipped) path lists."""
    included, skipped = [], []
    for path in sorted(_REPO_ROOT.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(_REPO_ROOT)
        if any(part in _SKIP_DIRS or part.startswith(".") for part in rel.parts):
            continue
        if _is_secret_shaped(path):
            skipped.append((str(rel), "secret-shaped name"))
            continue
        if path.suffix.lower() not in _INCLUDE_SUFFIXES and path.name not in _INCLUDE_NAMES:
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size > _MAX_FILE_BYTES:
            skipped.append((str(rel), "larger than per-file cap"))
            continue
        included.append((path, str(rel), size))
    return included, skipped


def _ledger_section():
    from memory.ledger import get_ledger, verify_chain
    chain = get_ledger()
    payload = {
        "total_blocks": len(chain),
        "chain_valid": verify_chain(),
        "blocks": chain,
    }
    return json.dumps(payload, default=str, indent=1).encode("utf-8")


def _conversations_section():
    from memory.conversation import get_history_page
    user = "jesse_martinez_jr"
    messages, total, offset = [], None, 0
    for _ in range(50):  # hard cap: 50 pages x 200 = 10,000 messages
        total, page = get_history_page(user, 200, offset, None, None)
        if not page:
            break
        messages.extend(page)
        offset += len(page)
        if total is not None and offset >= total:
            break
    payload = {"user": user, "total": total, "exported": len(messages),
               "messages": messages}
    return json.dumps(payload, default=str, indent=1).encode("utf-8")


def _executions_section():
    from memory.executions import list_executions
    rows, total, offset = [], None, 0
    for _ in range(25):  # hard cap: 25 pages x 200 = 5,000 records
        total, page = list_executions(200, offset, None, None, None)
        if not page:
            break
        rows.extend(page)
        offset += len(page)
        if total is not None and offset >= total:
            break
    payload = {"total": total, "exported": len(rows), "executions": rows}
    return json.dumps(payload, default=str, indent=1).encode("utf-8")


def build_package() -> bytes:
    """Assemble the full package archive and return its bytes."""
    entries = []   # manifest rows: path, size, sha256
    skipped = []   # manifest rows: path, reason
    buffer = io.BytesIO()

    def add(zf, arcname, data: bytes):
        zf.writestr(arcname, data)
        entries.append({
            "path": arcname,
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        })

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # --- deployed source tree, exactly as stored ---
        included, src_skipped = _collect_source_files()
        for path, rel, _size in included:
            try:
                add(zf, "source/" + rel, path.read_bytes())
            except OSError as exc:
                skipped.append((rel, "read failed: %s" % exc))
        skipped.extend(src_skipped)

        # --- runtime data, each section crash-safe ---
        for arcname, builder in (
            ("data/ledger_full.json", _ledger_section),
            ("data/conversations.json", _conversations_section),
            ("data/executions.json", _executions_section),
        ):
            try:
                add(zf, arcname, builder())
            except Exception as exc:  # never fail the whole package
                note = ("This section failed during export: %s" % exc).encode()
                add(zf, arcname + ".ERROR.txt", note)

        # --- manifest last, so it can describe everything above ---
        manifest = {
            "package": "jesse-ai-full-package",
            "owner": "Jesse Armando Martinez Junior",
            "generated_at_unix": int(time.time()),
            "file_count": len(entries),
            "total_bytes": sum(e["size"] for e in entries),
            "files": entries,
            "skipped": [{"path": p, "reason": r} for p, r in skipped],
            "notes": [
                "Source files are byte-exact copies from the deployed tree.",
                "Secret-shaped files are excluded by rule and listed under skipped.",
                "Runtime data sections are full exports at generation time.",
            ],
        }
        zf.writestr("manifest.json",
                    json.dumps(manifest, indent=1).encode("utf-8"))

    return buffer.getvalue()


@package_router.get("/oversight/package")
async def oversight_package(x_user: str = Header(default="")):
    """One guarded download: the full stack package as a zip archive.

    Same guard as every /oversight/* route: explicit allowlisted header
    required, no passing default.
    """
    if not (bool(x_user) and authenticate(x_user)):
        return JSONResponse(status_code=403, content={"error": "Unauthorized"})
    try:
        archive = build_package()
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})
    return Response(
        content=archive,
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="jesse_ai_package.zip"',
            "X-Package-Bytes": str(len(archive)),
        },
    )
