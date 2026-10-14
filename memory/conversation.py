"""
Sovereign Conversation Memory — Immutable, Per-User, Never-Forgetting
Owner: SLMK Jesse Martinez Junior
v6: Every message is sealed as a ledger block. Append-only.
    Postgres is source of truth when DATABASE_URL is set.
    In-memory store is fallback cache. Nothing is ever deleted.
"""
import time
import os
import json

DATABASE_URL = os.environ.get("DATABASE_URL", "")

_pg_conn = None
_mem_store: dict = {}


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
            c.execute("""CREATE TABLE IF NOT EXISTS conversations (
                id SERIAL PRIMARY KEY,
                username TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                ts DOUBLE PRECISION NOT NULL,
                block_hash TEXT,
                block_index INTEGER
            )""")
            c.execute("CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations (username, id)")
        return _pg_conn
    except Exception:
        _pg_conn = None
        return None


def add_message(user: str, role: str, content: str) -> dict:
    """
    Append a conversation message. Seals it as an immutable ledger block.
    role is 'user' or 'assistant'. Never updates. Never deletes.
    """
    from memory.ledger import create_event
    ts = time.time()
    block = create_event({
        "type": "conversation",
        "user": user,
        "role": role,
        "content": content[:4000],
    })
    msg = {
        "user": user,
        "role": role,
        "content": content,
        "ts": ts,
        "block_hash": block["block_hash"],
        "block_index": block["index"],
    }
    conn = _pg()
    if conn is not None:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO conversations (username, role, content, ts, block_hash, block_index) "
                    "VALUES (%s,%s,%s,%s,%s,%s)",
                    (user, role, content, ts, block["block_hash"], block["index"]),
                )
        except Exception:
            pass
    _mem_store.setdefault(user, []).append(msg)
    return msg


def get_history(user: str, limit: int = 20) -> list:
    """Return the most recent messages for a user, oldest first. Never forgets."""
    conn = _pg()
    if conn is not None:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT username, role, content, ts, block_hash, block_index "
                    "FROM conversations WHERE username = %s "
                    "ORDER BY id DESC LIMIT %s",
                    (user, limit),
                )
                rows = cur.fetchall()
            msgs = [
                {"user": r[0], "role": r[1], "content": r[2], "ts": r[3],
                 "block_hash": r[4], "block_index": r[5]}
                for r in rows
            ]
            msgs.reverse()
            return msgs
        except Exception:
            pass
    return list(_mem_store.get(user, [])[-limit:])


def format_history_for_prompt(user: str, limit: int = 10) -> str:
    """Format recent conversation as LLM prompt context."""
    history = get_history(user, limit)
    if not history:
        return ""
    lines = ["[Sovereign conversation memory — these are prior turns with the Superadmin. Never forget them:]"]
    for m in history:
        tag = "SUPERADMIN" if m["role"] == "user" else "Jesse AI"
        lines.append(f"{tag}: {m['content'][:1500]}")
    return "\n".join(lines)


def count_messages(user: str) -> int:
    """Total stored messages for a user (Postgres if available)."""
    conn = _pg()
    if conn is not None:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM conversations WHERE username = %s", (user,))
                return cur.fetchone()[0]
        except Exception:
            pass
    return len(_mem_store.get(user, []))
