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
"""
import hashlib
import json
import os
import time

DATABASE_URL = os.environ.get("DATABASE_URL", "")

_pg_conn = None
_mem_store: list = []


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
    conn = _pg()
    if conn is not None:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO executions (ts, username, kind, command, ledger_index, "
                    "stack_execution, build_result, jesse_ai_response, spoken_response, response_hash) "
                    "VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s) RETURNING id",
                    (ts, username, kind, command, ledger_index,
                     json.dumps(stack_execution, default=str) if stack_execution is not None else None,
                     json.dumps(build_result, default=str) if build_result is not None else None,
                     jesse_ai_response, spoken_response, response_hash),
                )
                record["id"] = cur.fetchone()[0]
        except Exception as e:
            log_event(f"[EXECUTIONS] Postgres insert failed: {e}", "warning")
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


def list_executions(limit=50, offset=0, kind=None, since_block=None, until_block=None):
    """Paginated execution index, oldest first. Returns (total, rows)."""
    where, params = _filters(kind, since_block, until_block)
    conn = _pg()
    if conn is not None:
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
            pass
    rows = list(_mem_store)
    if kind:
        rows = [r for r in rows if r["kind"] == kind]
    if since_block is not None:
        rows = [r for r in rows if r["ledger_index"] is not None and r["ledger_index"] >= since_block]
    if until_block is not None:
        rows = [r for r in rows if r["ledger_index"] is not None and r["ledger_index"] <= until_block]
    return len(rows), rows[offset:offset + limit]


def get_execution(exec_id):
    """One full execution record by id, or None."""
    conn = _pg()
    if conn is not None:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, ts, username, kind, command, ledger_index, "
                    "stack_execution, build_result, jesse_ai_response, spoken_response, response_hash "
                    "FROM executions WHERE id = %s",
                    (exec_id,),
                )
                row = cur.fetchone()
            if row is not None:
                return _row_to_record(row)
        except Exception:
            pass
    for r in _mem_store:
        if r["id"] == exec_id:
            return r
    return None
