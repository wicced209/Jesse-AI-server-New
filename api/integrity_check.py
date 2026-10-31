"""
CRSMCPAI Alpha - Module Integrity Verification (anti-distillation build 1)

Purpose: prove the deployed code is the code that was sealed. Every
source file in the running tree is hashed (SHA-256, the package
manifest convention). The baseline is a full path-to-hash map sealed
into the Golden Ledger as INTEGRITY_BASELINE. Verification recomputes
the tree and compares: changed, missing, and added files are named.

Rules that keep this honest:
- The baseline NEVER updates itself. A restart or a redeploy cannot
  bless a changed file. A new baseline is sealed only by an explicit
  owner call (rebaseline), which is itself a sealed act.
- On startup the baseline is rebuilt by replaying INTEGRITY_BASELINE
  seals from the ledger; the LAST one wins (each names its parent).
- A mismatch seals INTEGRITY_ALERT, throttled so the same drift set
  is not re-sealed on every check (the set's fingerprint is kept in
  memory; a changed drift set seals again).

State note: the ledger is the source of truth for the baseline. The
in-memory alert-throttle resets on restart by design.
"""

import hashlib
import json
import os

_scan_fn = None          # injected: () -> ledger entries (list of dicts)
_seal_fn = None          # injected: (event_type, payload) -> seal result
_root_dir = None         # injected: absolute path of the app source root

_BASELINE = {"files": {}, "root": "", "ledger_index": None, "file_count": 0}
_BASELINE_LOADED = False
_LAST_ALERT_FP = ""


def set_scan_fn(fn):
    global _scan_fn
    _scan_fn = fn


def set_seal_fn(fn):
    global _seal_fn
    _seal_fn = fn


def set_root_dir(path):
    global _root_dir
    _root_dir = path


def _sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _root_fingerprint(files):
    canon = json.dumps(files, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()


def compute_tree(root_dir):
    """Hash every .py file under root_dir. Returns {relpath: sha256}."""
    out = {}
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames
                       if d != "__pycache__" and not d.startswith(".")]
        for name in filenames:
            if not name.endswith(".py"):
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root_dir).replace(os.sep, "/")
            try:
                with open(full, "rb") as f:
                    out[rel] = _sha256_bytes(f.read())
            except OSError:
                continue
    return out


def _seal(event_type, payload):
    """House convention: the injected seal fn takes ONE event dict and
    returns nothing (server.py's _device_seal -> ledger.create_event).
    Fresh seal indexes are recovered by reloading from the ledger."""
    if _seal_fn is None:
        return None
    event = dict(payload)
    event["event"] = event_type
    try:
        return _seal_fn(event)
    except Exception:
        return None


def _payload_of(entry):
    if isinstance(entry, dict):
        p = entry.get("payload")
        if isinstance(p, dict):
            return p
    return {}


def load_baseline():
    """Rebuild the baseline from the ledger (last INTEGRITY_BASELINE wins)."""
    global _BASELINE_LOADED
    if _scan_fn is None or _root_dir is None:
        return dict(_BASELINE)
    try:
        entries = _scan_fn() or []
    except Exception:
        entries = []
    found = None
    for entry in entries:
        p = _payload_of(entry)
        if p.get("event") == "INTEGRITY_BASELINE" and isinstance(
                p.get("files"), dict):
            found = (p, entry.get("index"))
    if found:
        p, idx = found
        _BASELINE["files"] = dict(p["files"])
        _BASELINE["root"] = p.get("root", "")
        _BASELINE["file_count"] = len(p["files"])
        _BASELINE["ledger_index"] = idx
    _BASELINE_LOADED = True
    return dict(_BASELINE)


def ensure_baseline():
    """Seal the first baseline if none exists in the ledger. Owner-side
    act performed at wiring time; NOT a silent self-update: it fires
    only when the ledger holds no baseline at all."""
    load_baseline()
    if _BASELINE["file_count"]:
        return {"ok": True, "created": False,
                "ledger_index": _BASELINE["ledger_index"],
                "file_count": _BASELINE["file_count"]}
    files = compute_tree(_root_dir)
    root = _root_fingerprint(files)
    _seal("INTEGRITY_BASELINE", {
        "files": files,
        "file_count": len(files),
        "root": root,
        "parent_baseline": None,
    })
    load_baseline()
    _BASELINE.update({"files": files, "root": root,
                      "file_count": len(files)})
    return {"ok": True, "created": True,
            "ledger_index": _BASELINE["ledger_index"],
            "file_count": len(files), "root": root}


def rebaseline(user):
    """Owner-only: seal a NEW baseline over the current tree (after a
    legitimate deploy). Names the previous baseline it replaces."""
    if not user:
        return {"ok": False, "error": "user required"}
    load_baseline()
    files = compute_tree(_root_dir)
    root = _root_fingerprint(files)
    _seal("INTEGRITY_BASELINE", {
        "files": files,
        "file_count": len(files),
        "root": root,
        "parent_baseline": _BASELINE["ledger_index"],
        "sealed_by": user,
    })
    load_baseline()
    _BASELINE.update({"files": files, "root": root,
                      "file_count": len(files)})
    return {"ok": True, "created": True,
            "ledger_index": _BASELINE["ledger_index"],
            "file_count": len(files), "root": root}


def verify(seal_alert=True):
    """Recompute the tree and compare against the sealed baseline."""
    load_baseline()
    base = _BASELINE["files"]
    now = compute_tree(_root_dir)
    changed = sorted(p for p in base if p in now and now[p] != base[p])
    missing = sorted(p for p in base if p not in now)
    added = sorted(p for p in now if p not in base)
    clean = not (changed or missing or added)
    result = {
        "ok": True,
        "clean": clean,
        "baseline_file_count": len(base),
        "current_file_count": len(now),
        "baseline_ledger_index": _BASELINE["ledger_index"],
        "changed": changed,
        "missing": missing,
        "added": added,
        "current_root": _root_fingerprint(now),
    }
    if not clean and seal_alert:
        fp = hashlib.sha256(json.dumps(
            {"c": changed, "m": missing, "a": added},
            sort_keys=True).encode()).hexdigest()
        global _LAST_ALERT_FP
        if fp != _LAST_ALERT_FP:
            _LAST_ALERT_FP = fp
            _seal("INTEGRITY_ALERT", {
                "changed": changed,
                "missing": missing,
                "added": added,
                "baseline_ledger_index": _BASELINE["ledger_index"],
            })
            result["alert_sealed"] = True
    return result


def integrity_status():
    load_baseline()
    return {
        "ok": True,
        "module": "integrity_check",
        "baseline_sealed": bool(_BASELINE["file_count"]),
        "baseline_file_count": _BASELINE["file_count"],
        "baseline_ledger_index": _BASELINE["ledger_index"],
        "baseline_root": _BASELINE["root"],
        "honesty": "The baseline is sealed in the ledger and never "
                   "updates itself; a new baseline is an explicit, "
                   "sealed owner act after a legitimate deploy.",
    }
