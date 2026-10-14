"""
Golden Ledger V28 — Immutable SHA3-512 Hash-Chained Event Log
Owner: SLMK Jesse Martinez Junior
v6: Restored V28 file pattern + Postgres for permanent eternal storage.
    Postgres is source of truth when DATABASE_URL is set.
    File (golden_ledger.json) is local backup. Memory is cache.
    Append-only. No update. No delete. Never forgets.
"""
import hashlib
import json
import time
import os

GENESIS = "92038cafccc7192535bd475cca985d03000d89962b8dc96f6664081663559b1b"
OWNER = "jesse_martinez_jr"
LEDGER_FILE = os.path.join(os.path.dirname(__file__), "golden_ledger.json")
DATABASE_URL = os.environ.get("DATABASE_URL", "")

_pg_conn = None
_ledger_cache: list = []


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
        return [
            {"index": r[0], "ts": r[1], "owner": r[2], "payload": r[3],
             "prev_hash": r[4], "block_hash": r[5]}
            for r in rows
        ]
    except Exception:
        return None


def _save_pg(block):
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
        return True
    except Exception:
        return False


def _get_chain():
    """Postgres is source of truth. Then memory cache. Then file backup."""
    pg_chain = _load_pg()
    if pg_chain is not None:
        return pg_chain
    if _ledger_cache:
        return _ledger_cache
    file_chain = _load_file()
    if file_chain:
        _ledger_cache.extend(file_chain)
    return _ledger_cache


def create_event(payload: dict) -> dict:
    """
    Append a new event to the immutable ledger.
    Each block is SHA3-512 chained to the previous block's hash,
    anchored to the sovereign genesis seal.
    """
    chain = _get_chain()
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
    pg_ok = _save_pg(block)
    if chain is _ledger_cache:
        chain.append(block)
    else:
        _ledger_cache.clear()
        _ledger_cache.extend(chain)
        _ledger_cache.append(block)
        chain = _ledger_cache
    if not pg_ok:
        _save_file(chain)
    return block


def get_ledger() -> list:
    """Return a copy of the full ledger chain."""
    return list(_get_chain())


def verify_chain() -> bool:
    """
    Walk the chain and verify every block's hash and linkage.
    Returns True if the ledger is intact, False if tampered.
    """
    chain = _get_chain()
    if not chain:
        return True
    if chain[0]["prev_hash"] != GENESIS:
        return False
    for i, block in enumerate(chain):
        stored = block.get("block_hash")
        check = {k: v for k, v in block.items() if k != "block_hash"}
        expected = hashlib.sha3_512(
            json.dumps(check, sort_keys=True).encode()
        ).hexdigest()
        if stored != expected:
            return False
        if i > 0 and block.get("prev_hash") != chain[i - 1].get("block_hash"):
            return False
    return True
