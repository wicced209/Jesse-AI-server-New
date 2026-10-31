"""
CRSMCPAI Alpha - Output Watermark & Answer Provenance
(anti-distillation build 4, v2)

Two layers, because measurement demanded it:

V1 measured: a word-choice watermark (keyed contraction choices -
"do not" vs "don't") is screen-reader safe and meaning-exact, but
on this system's real demo answers (formal register) it found ZERO
usable sites per answer. A mark that never fires is not a mark.
The contraction layer is kept (it fires when sites exist), but the
primary mechanism is the one this stack is actually built on:

PROVENANCE BY SEALED RECORD. Every public answer served is
fingerprinted into the immutable ledger (ANSWER_FINGERPRINT: a
SHA3-512 of the exact served text and of a normalized form - case,
spacing and punctuation removed). Verification recomputes the
fingerprints of a candidate text and checks membership in the
sealed set, which is rebuilt from the ledger on first use, the
same replay pattern the credentials registry uses. A verbatim
republication matches the exact tier; a copy with case, spacing or
punctuation edits still matches the normalized tier; rewording
defeats both - stated plainly, not hidden.

The contraction layer: which form appears at each contraction site
is chosen by a keyed hash of the answer skeleton; a verbatim copy
preserves the pattern. Key from CRS_WATERMARK_KEY when set, else
ephemeral per boot (commitment sealed either way, key never
stored). All choices are meaning-identical and screen-reader safe:
no invisible characters, no spacing tricks in the text itself.

Nothing here blocks, bans or alters meaning. It produces evidence.
"""

import hashlib
import hmac as hmac_mod
import os
import re
import secrets

_seal_fn = None
_scan_fn = None

PAIRS = [
    ("do not", "don't"),
    ("does not", "doesn't"),
    ("did not", "didn't"),
    ("cannot", "can't"),
    ("could not", "couldn't"),
    ("would not", "wouldn't"),
    ("should not", "shouldn't"),
    ("is not", "isn't"),
    ("are not", "aren't"),
    ("it is", "it's"),
    ("that is", "that's"),
    ("there is", "there's"),
    ("you are", "you're"),
    ("we are", "we're"),
    ("you will", "you'll"),
    ("it will", "it'll"),
]

_PATTERNS = []
for a, b in PAIRS:
    for form, other in ((a, b), (b, a)):
        _PATTERNS.append((re.compile(r"\b" + re.escape(form) + r"\b",
                                     re.IGNORECASE), form, other))

_key = None
_key_source = None
_commitment_sealed = False
_marked_count = 0
_unmarked_count = 0

_EXACT = set()
_NORMALIZED = set()
_registry_ready = False
_registered_count = 0


def set_seal_fn(fn):
    global _seal_fn
    _seal_fn = fn


def set_scan_fn(fn):
    global _scan_fn
    _scan_fn = fn


def _seal(event):
    if _seal_fn is None:
        return
    try:
        _seal_fn(event)
    except Exception:
        pass


def _payload_of(block):
    if not isinstance(block, dict):
        return None
    p = block.get("payload")
    return p if isinstance(p, dict) else None


def _ensure_registry():
    global _registry_ready
    if _registry_ready:
        return
    _registry_ready = True
    if _scan_fn is None:
        return
    try:
        blocks = _scan_fn() or []
    except Exception:
        return
    for block in blocks:
        p = _payload_of(block)
        if not p or p.get("event") != "ANSWER_FINGERPRINT":
            continue
        if p.get("exact"):
            _EXACT.add(p["exact"])
        if p.get("normalized"):
            _NORMALIZED.add(p["normalized"])


def normalize(text):
    t = re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower())
    return re.sub(r"\s+", " ", t).strip()


def _fp(text):
    return hashlib.sha3_512(text.encode()).hexdigest()


def register_answer(text, source_tag=""):
    """Seal the served answer's fingerprints (once per answer)."""
    global _registered_count
    _ensure_registry()
    if not text:
        return
    exact = _fp(text)
    if exact in _EXACT:
        return
    norm = _fp(normalize(text))
    _EXACT.add(exact)
    _NORMALIZED.add(norm)
    _registered_count += 1
    _seal({"event": "ANSWER_FINGERPRINT", "exact": exact,
           "normalized": norm, "source_tag": source_tag})


def _ensure_key():
    global _key, _key_source, _commitment_sealed
    if _key is not None:
        return
    env = os.environ.get("CRS_WATERMARK_KEY", "")
    if env:
        _key = env.encode()
        _key_source = "environment"
    else:
        _key = secrets.token_bytes(32)
        _key_source = "ephemeral_per_boot"
    if not _commitment_sealed:
        _commitment_sealed = True
        _seal({"event": "WATERMARK_KEY_COMMITMENT",
               "key_commitment": hashlib.sha3_512(_key).hexdigest(),
               "key_source": _key_source})


def _sites(text):
    found = []
    for pat, form, other in _PATTERNS:
        for m in pat.finditer(text):
            token_zone = text[max(0, m.start() - 12):m.end() + 4]
            if "://" in token_zone or "`" in token_zone:
                continue
            found.append((m.start(), m.end(), m.group(0), other))
    found.sort()
    out, last_end = [], -1
    for s in found:
        if s[0] >= last_end:
            out.append(s)
            last_end = s[1]
    return out


def _skeleton(text, sites):
    parts, prev = [], 0
    for s, e, _, _ in sites:
        parts.append(text[prev:s])
        parts.append("\x00SITE\x00")
        prev = e
    parts.append(text[prev:])
    return "".join(parts)


def _expected_bits(skeleton, n):
    digest = hmac_mod.new(_key, skeleton.encode(),
                          hashlib.sha256).digest()
    bits = []
    i = 0
    while len(bits) < n:
        for byte in digest:
            for shift in range(7, -1, -1):
                bits.append((byte >> shift) & 1)
        i += 1
        digest = hmac_mod.new(_key, (skeleton + str(i)).encode(),
                              hashlib.sha256).digest()
    return bits[:n]


def _match_case(original, replacement):
    if original[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def mark(text):
    """Apply the keyed contraction pattern where sites exist."""
    global _marked_count, _unmarked_count
    _ensure_key()
    if not text:
        return text
    sites = _sites(text)
    if len(sites) < 3:
        _unmarked_count += 1
        return text
    bits = _expected_bits(_skeleton(text, sites), len(sites))
    parts, prev = [], 0
    for (s, e, current, other), bit in zip(sites, bits):
        parts.append(text[prev:s])
        long_form = current if current.lower() in (
            p[0] for p in PAIRS) else other
        short_form = other if long_form == current else current
        chosen = short_form if bit == 1 else long_form
        parts.append(_match_case(current, chosen))
        prev = e
    parts.append(text[prev:])
    _marked_count += 1
    return "".join(parts)


def verify(text):
    """Tiered provenance check: sealed exact, sealed normalized,
    then the word-choice pattern."""
    _ensure_key()
    _ensure_registry()
    text = text or ""
    if _fp(text) in _EXACT:
        return {"marked": True, "tier": "exact_sealed_record",
                "reason": "fingerprint matches a sealed answer record"}
    if _fp(normalize(text)) in _NORMALIZED:
        return {"marked": True, "tier": "normalized_sealed_record",
                "reason": "normalized fingerprint matches a sealed "
                          "answer record (case, spacing or "
                          "punctuation edits only)"}
    sites = _sites(text)
    if len(sites) >= 4:
        bits = _expected_bits(_skeleton(text, sites), len(sites))
        matched = sum(1 for (_, _, cur, _), bit in zip(sites, bits)
                      if (bit == 1) == ("'" in cur))
        ratio = matched / len(sites)
        if ratio >= 0.85:
            return {"marked": True, "tier": "word_choice_pattern",
                    "sites": len(sites), "matched": matched,
                    "ratio": round(ratio, 3),
                    "reason": "contraction pattern matches this "
                              "boot's key"}
    return {"marked": False, "tier": None,
            "reason": "no sealed fingerprint and no pattern match"}


def watermark_status():
    _ensure_key()
    _ensure_registry()
    return {
        "ok": True,
        "module": "output_watermark",
        "primary_mechanism": "sealed answer fingerprints",
        "sealed_answers_in_registry": len(_EXACT),
        "answers_registered_this_boot": _registered_count,
        "word_choice_key_source": _key_source,
        "answers_pattern_marked_this_boot": _marked_count,
        "answers_without_sites_this_boot": _unmarked_count,
        "honesty": "Provenance evidence, not DRM. Verbatim copies "
                   "match the exact sealed fingerprint; copies with "
                   "case, spacing or punctuation edits match the "
                   "normalized tier; reworded copies match neither - "
                   "the sealed record still proves what we served "
                   "and when. The contraction pattern is a bonus "
                   "layer that fires only when an answer has enough "
                   "contraction sites (rare in formal prose).",
    }
