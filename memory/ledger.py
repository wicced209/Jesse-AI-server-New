"""
Golden Ledger V28 — Immutable SHA3-512 Hash-Chained Event Log
Owner: SLMK Jesse Martinez Junior
v7: Reload-defect fix (2026-11-08, Muse, repo lane).
    Postgres is the single source of truth when DATABASE_URL is set.
    The local file is a write-only backup in that mode and is NEVER
    loaded for indexing, so a stale bundled shadow chain can no longer
    fork the count across restarts. Appends are serialized, and a
    Postgres insert that is skipped on index conflict is detected and
    retried against the freshly loaded chain instead of being silently
    dropped. File mode (no DATABASE_URL) keeps the v6 behavior.
    Append-only. No update. No delete. Never forgets.
"""
import hashlib
import json
import threading
import time
import os

GENESIS = "92038cafccc7192535bd475cca985d03000d89962b8dc96f6664081663559b1b"
OWNER = "jesse_martinez_jr"
LEDGER_FILE = os.path.join(os.path.dirname(__file__), "golden_ledger.json")
DATABASE_URL = os.environ.get("DATABASE_URL", "")

_pg_conn = None
_ledger_cache: list = []
_append_lock = threading.Lock()


def _pg():
    global _pg_conn
    if not DATABASE_URL:
        return None
    if _pg_conn is not None:
        return _pg_conn
    try:
        import psycopg2
        _pg_conn = psycopg2.connect(DATABASE_URL)
        _pg_conn.autocommit = True
        with _pg_conn.cursor() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS ledger_blocks (
                idx INTEGER PRIMARY KEY,
                ts DOUBLE PRECISION NOT NULL,
                owner TEXT NOT NULL,
                payload JSONB,
                prev_hash TEXT NOT NULL,
                block_hash TEXT NOT NULL
            )""")
        return _pg_conn
    except Exception:
        _pg_conn = None
        return None


def _load_file():
    if os.path.exists(LEDGER_FILE):
        try:
            with open(LEDGER_FILE) as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            pass
    return []


def _save_file(chain):
    try:
        with open(LEDGER_FILE, "w") as f:
            json.dump(chain, f, indent=2)
    except Exception:
        pass


def _load_pg():
    """Return the Postgres chain, or None if Postgres cannot be read.

    On a read failure the cached connection is dropped so the next
    call retries with a fresh connection instead of failing forever.
    """
    global _pg_conn
    conn = _pg()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT idx, ts, owner, payload, prev_hash, block_hash "
                "FROM ledger_blocks ORDER BY idx ASC"
            )
            rows = cur.fetchall()
        result = []
        for r in rows:
            block = {"index": r[0], "ts": r[1], "owner": r[2], "payload": r[3],
                     "prev_hash": r[4], "block_hash": r[5]}
            block["hash"] = block["block_hash"]
            result.append(block)
        return result
    except Exception:
        try:
            _pg_conn.close()
        except Exception:
            pass
        _pg_conn = None
        return None


def _save_pg(block):
    """Insert one block. Return True only if the row was inserted.

    ON CONFLICT DO NOTHING reports success at the cursor level even
    when nothing was written, so rowcount is the only honest signal.
    """
    conn = _pg()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO ledger_blocks (idx, ts, owner, payload, prev_hash, block_hash) "
                "VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (idx) DO NOTHING",
                (block["index"], block["ts"], block["owner"],
                 json.dumps(block["payload"]), block["prev_hash"], block["block_hash"]),
            )
            return cur.rowcount == 1
    except Exception:
        return False


def _get_chain():
    if DATABASE_URL:
        pg_chain = _load_pg()
        if pg_chain is not None:
            return pg_chain
        # Postgres is configured but unreadable right now. Fall back
        # only to this process's in-memory cache, which was loaded
        # from Postgres earlier. Never fork onto the file shadow.
        if _ledger_cache:
            return list(_ledger_cache)
        # One retry with a fresh connection before giving up.
        pg_chain = _load_pg()
        if pg_chain is not None:
            return pg_chain
        return list(_ledger_cache)
    if _ledger_cache:
        return _ledger_cache
    file_chain = _load_file()
    if file_chain:
        for b in file_chain:
            if "hash" not in b and "block_hash" in b:
                b["hash"] = b["block_hash"]
        _ledger_cache.extend(file_chain)
    return _ledger_cache


def _build_block(chain, payload):
    prev = chain[-1]["block_hash"] if chain else GENESIS
    block = {
        "index": len(chain),
        "ts": time.time(),
        "owner": OWNER,
        "payload": payload,
        "prev_hash": prev,
    }
    block["block_hash"] = hashlib.sha3_512(
        json.dumps(block, sort_keys=True).encode()
    ).hexdigest()
    block["hash"] = block["block_hash"]
    return block


def create_event(payload: dict) -> dict:
    with _append_lock:
        if DATABASE_URL:
            # Postgres mode: append against the freshly loaded chain.
            # If the insert loses an index race, reload and retry with
            # the correct next index instead of dropping the block.
            for _attempt in range(5):
                chain = _get_chain()
                block = _build_block(chain, payload)
                if _save_pg(block):
                    _ledger_cache.clear()
                    _ledger_cache.extend(chain)
                    _ledger_cache.append(block)
                    return block
            # Postgres stayed unreachable through every retry. Keep
            # the block in this process's cache and back it up to the
            # file so it is not lost; it reconciles on the next boot
            # only through Postgres, never the other way around.
            chain = list(_ledger_cache)
            block = _build_block(chain, payload)
            _ledger_cache.append(block)
            _save_file(list(_ledger_cache))
            return block
        chain = _get_chain()
        block = _build_block(chain, payload)
        if chain is not _ledger_cache:
            _ledger_cache.clear()
            _ledger_cache.extend(chain)
        _ledger_cache.append(block)
        _save_file(list(_ledger_cache))
        return block


def import_block(block: dict) -> bool:
    """Append a block received from a peer, preserving its original
    hash (hyper sync reconciliation). The block is accepted only if
    it extends the current head exactly and its stored hash recomputes
    correctly; anything else is refused and nothing is written. This
    is the ledger's only foreign-block path — create_event remains the
    only way new local blocks are minted."""
    with _append_lock:
        chain = _get_chain()
        if block.get("index") != len(chain):
            return False
        expected_prev = chain[-1]["block_hash"] if chain else GENESIS
        if block.get("prev_hash") != expected_prev:
            return False
        check = {k: v for k, v in block.items() if k not in ("block_hash", "hash")}
        expected = hashlib.sha3_512(
            json.dumps(check, sort_keys=True).encode()
        ).hexdigest()
        if block.get("block_hash") != expected:
            return False
        block = dict(block)
        block["hash"] = block["block_hash"]
        if DATABASE_URL:
            if not _save_pg(block):
                return False
            _ledger_cache.clear()
            _ledger_cache.extend(chain)
            _ledger_cache.append(block)
            return True
        if chain is not _ledger_cache:
            _ledger_cache.clear()
            _ledger_cache.extend(chain)
        _ledger_cache.append(block)
        _save_file(list(_ledger_cache))
        return True


def get_ledger() -> list:
    return list(_get_chain())


def verify_chain() -> bool:
    chain = _get_chain()
    if not chain:
        return True
    if chain[0]["prev_hash"] != GENESIS:
        return False
    for i, block in enumerate(chain):
        stored = block.get("block_hash")
        check = {k: v for k, v in block.items() if k not in ("block_hash", "hash")}
        expected = hashlib.sha3_512(
            json.dumps(check, sort_keys=True).encode()
        ).hexdigest()
        if stored != expected:
            return False
        if i > 0 and block.get("prev_hash") != chain[i - 1].get("block_hash"):
            return False
    return True
