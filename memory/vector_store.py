"""
Vector memory — real embedding retrieval (v2, 2026-11-08, Muse).

Replaces the v1 substring filter. Every entry is embedded at store
time and retrieval ranks entries by cosine similarity to the query
embedding, most relevant first. No external model and no new
dependencies: the embedder is a deterministic local hashing embedder
(word unigrams + word bigrams + character trigrams, sublinear term
frequency, signed feature hashing into 384 dimensions, L2-normalized).
That is a real vector representation — it ranks by meaning-bearing
overlap (shared words, stems, and sub-word shape) instead of requiring
the query to appear verbatim — but it is NOT a learned semantic model.
The seam is explicit: pass any callable as EMBEDDER (or call
set_embedder) to swap in a model-backed embedder later without
touching callers.

Public API is unchanged from v1 so existing callers keep working:
    store_memory(data) -> entry {id, data, timestamp}
    retrieve_memory(query="") -> entries (all when no query; ranked,
        similarity-scored copies when a query is given)
    memory_count() -> int
Plus the explicit search API:
    search_memory(query, top_k=10, min_score=0.10) -> scored entries
    embed_text(text) -> the embedding vector (list of floats)

Storage remains in-process, as in v1; durability lives in the ledger
layer above this store (the memory agent seals every store there).
"""
import hashlib
import math
import re
import threading
import time

EMBED_DIM = 384
_DEFAULT_MIN_SCORE = 0.10

_memory_db: list[dict] = []
_vectors: list[list[float]] = []
_next_id = 1
_lock = threading.Lock()

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_SUFFIXES = ("ingly", "edly", "ing", "edly", "ed", "es", "s")
_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "with",
    "by", "at", "is", "are", "was", "were", "be", "been", "it", "its",
    "this", "that", "these", "those", "as", "from", "into", "does", "do",
    "how", "what", "which", "who", "when", "where", "why", "can", "could",
    "should", "would", "has", "have", "had", "not", "no", "yes",
})


def _stem(token: str) -> str:
    for suf in _SUFFIXES:
        if token.endswith(suf) and len(token) - len(suf) >= 3:
            return token[: -len(suf)]
    return token


def _features(text: str) -> list[str]:
    tokens = [
        _stem(t)
        for t in _TOKEN_RE.findall(text.lower())
        if len(t) >= 2 and t not in _STOPWORDS
    ]
    feats: list[str] = []
    feats.extend(tokens)
    feats.extend(f"{a}_{b}" for a, b in zip(tokens, tokens[1:]))
    for tok in tokens:
        padded = f"#{tok}#"
        feats.extend(padded[i: i + 3] for i in range(len(padded) - 2))
    return feats


def _hash_feature(feature: str) -> tuple[int, float]:
    digest = hashlib.sha3_256(feature.encode("utf-8")).digest()
    index = int.from_bytes(digest[:4], "little") % EMBED_DIM
    sign = 1.0 if digest[4] % 2 == 0 else -1.0
    return index, sign


def embed_text(text: str) -> list[float]:
    """Embed text into a normalized EMBED_DIM vector (local embedder)."""
    counts: dict[str, int] = {}
    for feat in _features(text or ""):
        counts[feat] = counts.get(feat, 0) + 1
    vec = [0.0] * EMBED_DIM
    for feat, count in counts.items():
        index, sign = _hash_feature(feat)
        vec[index] += sign * (1.0 + math.log(count))
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0.0:
        return vec
    return [v / norm for v in vec]


# Seam for a future model-backed embedder: any callable text -> vector.
EMBEDDER = embed_text


def set_embedder(fn) -> None:
    """Replace the embedder and re-embed everything already stored."""
    global EMBEDDER
    with _lock:
        EMBEDDER = fn
        _vectors.clear()
        _vectors.extend(EMBEDDER(entry["data"]) for entry in _memory_db)


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def store_memory(data: str) -> dict:
    """Store a text entry with its embedding and a timestamp."""
    global _next_id
    with _lock:
        entry = {
            "id":        _next_id,
            "data":      data,
            "timestamp": time.time(),
        }
        _next_id += 1
        _memory_db.append(entry)
        _vectors.append(EMBEDDER(data))
        return entry


def search_memory(query: str, top_k: int = 10, min_score: float = _DEFAULT_MIN_SCORE) -> list[dict]:
    """Return up to top_k entries ranked by cosine similarity to the
    query embedding, each as a copy carrying its 'score'. Entries below
    min_score are excluded, so an unrelated query returns nothing."""
    if not query:
        return []
    qv = EMBEDDER(query)
    with _lock:
        scored = [
            (score, entry)
            for entry, vec in zip(_memory_db, _vectors)
            if (score := _cosine(qv, vec)) >= min_score
        ]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    results = []
    for score, entry in scored[:top_k]:
        hit = dict(entry)
        hit["score"] = round(score, 4)
        results.append(hit)
    return results


def retrieve_memory(query: str = "") -> list[dict]:
    """
    Return stored memories. With no query, all entries in store order
    (v1 behavior, used by the memory agent's recall path). With a
    query, entries ranked by embedding similarity, best first.
    """
    if not query:
        with _lock:
            return list(_memory_db)
    return search_memory(query)


def memory_count() -> int:
    with _lock:
        return len(_memory_db)
