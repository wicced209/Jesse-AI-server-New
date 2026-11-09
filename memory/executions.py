"""
Sovereign Execution Oversight — Full Execution Records, Never Lost
Owner: SLMK Jesse Martinez Junior

Every /command and /build execution is recorded here in full: the complete
stack_execution / build_result, the Jesse AI response, and the spoken
rendering — so Muse (Jesse's eyes) can read back any past execution
complete and unabridged, not just the last 10 ledger blocks.

Postgres is source of truth when DATABASE_URL is set (same pattern as
memory/conversation.py and memory/ledger.py). In-memory list is fallback.
Nothing is ever deleted. A small ledger seal (EXECUTION_RECORDED) makes
each record tamper-evident against the golden chain without bloating the
chain with megabyte payloads. Recording never fails a command: every
failure is logged as a warning and swallowed by the caller.

v2: Mid-run empty-store fix (2026-11-08, Muse, repo lane).
    v1 cached its Postgres connection forever and, when any Postgres
    operation failed, silently fell through to the in-memory list —
    which a freshly restarted process has never hydrated from Postgres.
    When the host closed the idle connection mid-run (Neon does this),
    every read suddenly reported an empty store even though all records
    were intact in Postgres, and writes degraded to memory-only with
    fabricated ids. v2 mirrors memory/ledger.py v7: a failed operation
    drops the cached connection and retries once with a fresh one, so a
    dead connection heals on the next call instead of failing forever;
    appends are serialized under a lock and verified by the RETURNING
    id; the in-memory list is only a write-through cache of this
    process's own records and is consulted only when Postgres is not
    configured or stays unreachable through the retry.
"""
import hashlib
import json
import os
import threading
import time

DATABASE_URL = os.environ.get("DATABASE_URL", "")

_pg_conn = None
_mem_store: list = []
_lock = threading.Lock()


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
            c.execute("""CREATE TABLE IF NOT EXISTS executions (
                id SERIAL PRIMARY KEY,
                ts DOUBLE PRECISION NOT NULL,
                username TEXT NOT NULL,
                kind TEXT NOT NULL,
                command TEXT NOT NULL,
                ledger_index INTEGER,
                stack_execution JSONB,
                build_result JSONB,
                jesse_ai_response TEXT,
                spoken_response TEXT,
                response_hash TEXT
            )""")
            c.execute("CREATE INDEX IF NOT EXISTS idx_exec_user ON executions (username, id)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_exec_ledger ON executions (ledger_index)")
        return _pg_conn
    except Exception:
        _pg_conn = None
        return None


def _drop_conn():
    """Drop the cached connection after a failure so the next call
    retries with a fresh one instead of failing forever (ledger v7)."""
    global _pg_conn
    try:
        if _pg_conn is not None:
            _pg_conn.close()
    except Exception:
        pass
    _pg_conn = None


def _response_hash(stack_execution, build_result, jesse_ai_response, spoken_response):
    blob = json.dumps({
        "stack": stack_execution,
        "build": build_result,
        "response": jesse_ai_response or "",
        "spoken": spoken_response or "",
    }, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _row_to_record(r):
    def _as_obj(v):
        if v is None or isinstance(v, dict):
            return v
        try:
            return json.loads(v)
        except Exception:
            return None
    return {
        "id": r[0],
        "ts": r[1],
        "username": r[2],
        "kind": r[3],
        "command": r[4],
        "ledger_index": r[5],
        "stack_execution": _as_obj(r[6]),
        "build_result": _as_obj(r[7]),
        "jesse_ai_response": r[8],
        "spoken_response": r[9],
        "response_hash": r[10],
    }


def _insert_pg(record):
    """Insert one record into Postgres. Return the new row id, or None.

    On failure the cached connection is dropped and the insert is
    retried once with a fresh connection (ledger v7 discipline). The
    append counts as written only when RETURNING yields the row id.
    """
    last_err = None
    for _attempt in range(2):
        conn = _pg()
        if conn is None:
            return None
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO executions (ts, username, kind, command, ledger_index, "
                    "stack_execution, build_result, jesse_ai_response, spoken_response, response_hash) "
                    "VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s) RETURNING id",
                    (record["ts"], record["username"], record["kind"],
                     record["command"], record["ledger_index"],
                     json.dumps(record["stack_execution"], default=str)
                     if record["stack_execution"] is not None else None,
                     json.dumps(record["build_result"], default=str)
                     if record["build_result"] is not None else None,
                     record["jesse_ai_response"], record["spoken_response"],
                     record["response_hash"]),
                )
                row = cur.fetchone()
            if row is not None:
                return row[0]
            return None
        except Exception as e:
            last_err = e
            _drop_conn()
    if last_err is not None:
        from core.logger import log_event
        log_event(f"[EXECUTIONS] Postgres insert failed: {last_err}", "warning")
    return None


def record_execution(username, kind, command, ledger_index=None,
                     stack_execution=None, build_result=None,
                     jesse_ai_response=None, spoken_response=None):
    """Persist one full execution record. Never raises."""
    from core.logger import log_event
    ts = time.time()
    response_hash = _response_hash(
        stack_execution, build_result, jesse_ai_response, spoken_response)
    record = {
        "id": None,
        "ts": ts,
        "username": username,
        "kind": kind,
        "command": command,
        "ledger_index": ledger_index,
        "stack_execution": stack_execution,
        "build_result": build_result,
        "jesse_ai_response": jesse_ai_response,
        "spoken_response": spoken_response,
        "response_hash": response_hash,
    }
    with _lock:
        if DATABASE_URL:
            record["id"] = _insert_pg(record)
        if record["id"] is None:
            record["id"] = len(_mem_store) + 1
        _mem_store.append(record)
    try:
        from memory.ledger import create_event
        create_event({
            "event": "EXECUTION_RECORDED",
            "execution_id": record["id"],
            "ledger_index": ledger_index,
            "response_hash": response_hash,
        })
    except Exception as e:
        log_event(f"[EXECUTIONS] ledger seal failed: {e}", "warning")
    return record


def _filters(kind, since_block, until_block):
    clauses = []
    params = []
    if kind:
        clauses.append("kind = %s")
        params.append(kind)
    if since_block is not None:
        clauses.append("ledger_index >= %s")
        params.append(since_block)
    if until_block is not None:
        clauses.append("ledger_index <= %s")
        params.append(until_block)
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


def _list_pg(where, params, limit, offset):
    """One paginated Postgres read, or None if Postgres is unavailable.

    On failure the cached connection is dropped and the read is retried
    once with a fresh connection before giving up.
    """
    for _attempt in range(2):
        conn = _pg()
        if conn is None:
            return None
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM executions" + where, params)
                total = cur.fetchone()[0]
                cur.execute(
                    "SELECT id, ts, username, kind, command, ledger_index, "
                    "stack_execution, build_result, jesse_ai_response, spoken_response, response_hash "
                    "FROM executions" + where + " ORDER BY id ASC LIMIT %s OFFSET %s",
                    params + [limit, offset],
                )
                return total, [_row_to_record(r) for r in cur.fetchall()]
        except Exception:
            _drop_conn()
    return None


def list_executions(limit=50, offset=0, kind=None, since_block=None, until_block=None):
    """Paginated execution index, oldest first. Returns (total, rows)."""
    where, params = _filters(kind, since_block, until_block)
    if DATABASE_URL:
        with _lock:
            result = _list_pg(where, params, limit, offset)
        if result is not None:
            return result
        # Postgres is configured but stayed unreachable through the
        # retry. Fall back only to this process's own write-through
        # cache — never present it as the store while Postgres answers.
    rows = list(_mem_store)
    if kind:
        rows = [r for r in rows if r["kind"] == kind]
    if since_block is not None:
        rows = [r for r in rows if r["ledger_index"] is not None and r["ledger_index"] >= since_block]
    if until_block is not None:
        rows = [r for r in rows if r["ledger_index"] is not None and r["ledger_index"] <= until_block]
    return len(rows), rows[offset:offset + limit]


def _get_pg(exec_id):
    """One Postgres record by id: (found, record_or_None).

    found=False means Postgres could not be read at all (after the
    drop-and-retry), so the caller may consult the in-memory cache;
    found=True with None means Postgres answered and has no such row.
    """
    for _attempt in range(2):
        conn = _pg()
        if conn is None:
            return False, None
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, ts, username, kind, command, ledger_index, "
                    "stack_execution, build_result, jesse_ai_response, spoken_response, response_hash "
                    "FROM executions WHERE id = %s",
                    (exec_id,),
                )
                row = cur.fetchone()
            return True, (_row_to_record(row) if row is not None else None)
        except Exception:
            _drop_conn()
    return False, None


def get_execution(exec_id):
    """One full execution record by id, or None."""
    if DATABASE_URL:
        with _lock:
            found, record = _get_pg(exec_id)
        if found:
            if record is not None:
                return record
            # Postgres answered and has no such row; the row may still
            # be a cache-only record from a Postgres outage window.
            for r in _mem_store:
                if r["id"] == exec_id:
                    return r
            return None
    for r in _mem_store:
        if r["id"] == exec_id:
            return r
    return None
